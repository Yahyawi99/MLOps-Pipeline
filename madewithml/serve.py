import argparse
import os
import time
from http import HTTPStatus
from typing import Dict

import ray
from fastapi import FastAPI, Response
from ray import serve
from starlette.requests import Request

import json
from numpyencoder import NumpyEncoder

from madewithml import evaluate, predict
from madewithml.config import MLFLOW_TRACKING_URI, mlflow

# ── Metric names only — no prometheus objects at module level ─────────────────
# All prometheus objects are created inside _get_metrics() which is called at
# request time, AFTER cloudpickle has already serialized the app/class.
_metrics_cache = {}

def _get_metrics():
    """Return (or lazily create) prometheus metric objects.
    Called only at request time — never at import/pickle time.
    """
    if _metrics_cache:
        return _metrics_cache

    from prometheus_client import Counter, Histogram, CollectorRegistry
    registry = CollectorRegistry()  # isolated registry — no global thread locks

    _metrics_cache["REQUEST_COUNT"] = Counter(
        "http_requests_total",
        "Total HTTP Requests",
        ["method", "endpoint", "http_status"],
        registry=registry,
    )
    _metrics_cache["REQUEST_LATENCY"] = Histogram(
        "http_request_duration_seconds",
        "Request latency in seconds",
        ["endpoint"],
        buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
        registry=registry,
    )
    _metrics_cache["PREDICTION_COUNT"] = Counter(
        "model_predictions_total",
        "Count of predictions per class (drift detection)",
        ["predicted_class"],
        registry=registry,
    )
    _metrics_cache["THRESHOLD_FALLBACK_COUNT"] = Counter(
        "model_threshold_fallbacks_total",
        "Predictions that fell below threshold and were set to 'other'",
        registry=registry,
    )
    _metrics_cache["registry"] = registry
    return _metrics_cache


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Made With ML",
    description="Classify machine learning projects.",
    version="0.1",
)

@app.get("/metrics")
def metrics():
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    m = _get_metrics()
    return Response(generate_latest(m["registry"]), media_type=CONTENT_TYPE_LATEST)


@serve.deployment(num_replicas=1, ray_actor_options={"num_cpus": 0, "num_gpus": 0})
@serve.ingress(app)
class ModelDeployment:
    def __init__(self, run_id: str, threshold: float = 0.9):
        self.run_id = run_id
        self.threshold = threshold
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        
        # 🟩 BYPASS VERSION SKEW: Directly resolve the checkpoint directory location
        from urllib.parse import urlparse
        import pathlib
        from ray.train import Checkpoint
        
        artifact_uri = mlflow.get_run(run_id).info.artifact_uri
        artifact_dir = urlparse(artifact_uri).path
        
        # Scan for existing checkpoint directories within MLflow run artifacts
        checkpoint_dirs = sorted([str(p) for p in pathlib.Path(artifact_dir).rglob("checkpoint_*")])
        if not checkpoint_dirs:
            checkpoint_dirs = sorted([str(p) for p in pathlib.Path(artifact_dir).glob("checkpoint_*")])
            
        if not checkpoint_dirs:
            raise RuntimeError(f"No valid directory starting with 'checkpoint_' found in {artifact_dir}")
            
        # Target the latest tracked checkpoint directory
        best_checkpoint_dir = checkpoint_dirs[-1]
        print(f" Bypassed legacy loader. Instantiating checkpoint directly from: {best_checkpoint_dir}")
        
        best_checkpoint = Checkpoint.from_directory(best_checkpoint_dir)
        self.predictor = predict.TorchPredictor.from_checkpoint(best_checkpoint)

    @app.get("/")
    def _index(self) -> Dict:
        """Health check."""
        m = _get_metrics()
        m["REQUEST_COUNT"].labels(method="GET", endpoint="/", http_status=200).inc()
        return {
            "message": HTTPStatus.OK.phrase,
            "status-code": HTTPStatus.OK,
            "data": {},
        }

    @app.get("/run_id/")
    def _run_id(self) -> Dict:
        m = _get_metrics()
        m["REQUEST_COUNT"].labels(method="GET", endpoint="/run_id/", http_status=200).inc()
        return {"run_id": self.run_id}

    @app.post("/evaluate/")
    async def _evaluate(self, request: Request) -> Dict:
        start = time.time()
        m = _get_metrics()
        data = await request.json()
        results = evaluate.evaluate(run_id=self.run_id, dataset_loc=data.get("dataset"))
        m["REQUEST_LATENCY"].labels(endpoint="/evaluate/").observe(time.time() - start)
        m["REQUEST_COUNT"].labels(method="POST", endpoint="/evaluate/", http_status=200).inc()
        return {"results": results}

    @app.post("/predict/")
    async def _predict(self, request: Request):
        start = time.time()
        m = _get_metrics()

        data = await request.json()
        sample_ds = ray.data.from_items([{
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "tag": "other",
        }])
        results = predict.predict_proba(ds=sample_ds, predictor=self.predictor)

        for i, result in enumerate(results):
            pred = result["prediction"]
            prob = result["probabilities"]
            if prob[pred] < self.threshold:
                results[i]["prediction"] = "other"
                m["THRESHOLD_FALLBACK_COUNT"].inc()

            m["PREDICTION_COUNT"].labels(predicted_class=results[i]["prediction"]).inc()

        m["REQUEST_LATENCY"].labels(endpoint="/predict/").observe(time.time() - start)
        m["REQUEST_COUNT"].labels(method="POST", endpoint="/predict/", http_status=200).inc()

        safe_results = json.loads(json.dumps(results, cls=NumpyEncoder))
        return {"results": safe_results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_id", help="run ID to use for serving.")
    parser.add_argument("--threshold", type=float, default=0.9)
    args = parser.parse_args()

    ray.init(runtime_env={"env_vars": {"GITHUB_USERNAME": os.environ.get("GITHUB_USERNAME", "")}})

    # Configure proxy network parameters before startup
    serve.start(http_options={"host": "0.0.0.0", "port": 8000})

    # Execute the deployment binding cleanly
    serve.run(ModelDeployment.bind(run_id=args.run_id, threshold=args.threshold))

    while True:
        time.sleep(60)