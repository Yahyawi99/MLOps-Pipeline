pipeline {
    agent any

    environment {
        PYTHONUNBUFFERED = '1'
        PYTHONPATH = "${WORKSPACE}"
        GITHUB_USERNAME = 'Yahyawi99' 
        RAY_SERVE_PROXY_READY_CHECK_TIMEOUT_S = '120'
        RAY_DEDUP_LOGS = "0"
        RAY_TRAIN_ENABLE_V2_MIGRATION_WARNINGS = "0"
    }

    stages {
        // =========================================
        // 1. WORKLOADS WORKFLOW
        // =========================================
        stage('Model Development Workloads') {
            when {
                anyOf {
                     branch 'main'       
                     changeRequest()      
                 }
            }
            steps {
                echo "Securing Python 3.10 hermetic environment for training workloads..."
                sh '''#!/bin/bash
                    # 1. Define persistent cache directory for speed
                    export UV_CACHE_DIR="/var/jenkins_home/.uv_cache"
                    mkdir -p "$UV_CACHE_DIR"

                    # 2. Install uv package manager on host python
                    python3 -m pip install uv --break-system-packages

                    # 3. Establish the isolated runtime
                    uv venv .venv --python 3.10
                    
                    # 4. Install exact project dependencies with legacy setuptools compatibility
                    uv pip install "setuptools<81" -r requirements.txt

                    # 5. Clear out legacy tracking metrics written by mismatched global system versions
                    rm -rf mlruns/

                    # 6. Execute training on a single line to prevent whitespace/backslash parsing issues in Typer
                    .venv/bin/python3 madewithml/train.py --experiment-name "llm-classification" --dataset-loc "$(pwd)/datasets/dataset.csv" --train-loop-config '{"dropout_p": 0.5, "lr": 1e-4, "lr_factor": 0.8, "lr_patience": 3, "num_epochs": 1, "batch_size": 2}' --num-samples 20 --num-workers 1 --cpu-per-worker 1 --gpu-per-worker 0
                '''
            }
        }

        // ==========================================
        // 2. SERVE & DOCS WORKFLOW
        // ==========================================
        stage('Deploy and Document') {
            when {
                branch 'main'
                not { changeRequest() } 
            }
            steps {
                echo "Securing Python 3.10 hermetic execution environment with persistent caching..."

                sh '''#!/bin/bash
                    # 1. Define a persistent cache directory on the Jenkins host so downloads happen ONLY ONCE
                    export UV_CACHE_DIR="/var/jenkins_home/.uv_cache"
                    mkdir -p "$UV_CACHE_DIR"

                    # 2. Install uv tool securely on the host system python
                    python3 -m pip install uv --break-system-packages

                    # 3. Create an isolated Python 3.10 runtime environment
                    uv venv .venv --python 3.10
                    
                    # 4. Pin setuptools < 81 to preserve legacy pkg_resources compatibility
                    uv pip install "setuptools<81" -r requirements.txt

                    # 5. Prevent Jenkins from sweeping background tracking processes
                    export JENKINS_NODE_COOKIE=dontKillMe
                    
                    # 6. Extract the latest trained experiment run ID using the identical environment
                    LATEST_RUN_ID=$(.venv/bin/python3 -c "import mlflow; from madewithml.config import MLFLOW_TRACKING_URI; mlflow.set_tracking_uri(MLFLOW_TRACKING_URI); runs=mlflow.search_runs(experiment_names=['llm-classification']); print(runs.iloc[0].run_id if not runs.empty else '')")
                    
                    if [ -z "$LATEST_RUN_ID" ]; then
                        echo "Error: No MLflow runs found. You must train a model first!"
                        exit 1
                    fi
                    echo "Found Run ID: $LATEST_RUN_ID"
                    
                    # 7. Clean up any lingering ray background processes
                    .venv/bin/ray stop || true
                    
                    # 8. Start serving deployment in the background
                    nohup .venv/bin/python3 madewithml/serve.py --run_id $LATEST_RUN_ID > serve.log 2>&1 &
                    SERVE_PID=$!
                    
                    # 9. Server Health Check Verification Loop
                    echo "Waiting for Ray Serve to initialize on port 8000..."
                    TIMEOUT=120
                    ELAPSED=0
                    SLEEP_INTERVAL=2

                    while ! curl -s -f http://127.0.0.1:8000/ > /dev/null; do
                        if ! kill -0 $SERVE_PID 2>/dev/null; then
                            echo "❌ ERROR: serve.py crashed immediately on startup!"
                            echo "--- Printing serve.log for debugging ---"
                            cat serve.log
                            exit 1
                        fi

                        if [ $ELAPSED -ge $TIMEOUT ]; then
                            echo "❌ ERROR: Server failed to start within $TIMEOUT seconds!"
                            echo "--- Printing serve.log for debugging ---"
                            cat serve.log
                            exit 1
                        fi
                        
                        echo "Server not ready yet. Retrying in $SLEEP_INTERVAL seconds... ($ELAPSED/$TIMEOUT)"
                        sleep $SLEEP_INTERVAL
                        ELAPSED=$((ELAPSED + SLEEP_INTERVAL))
                    done
                    
                    echo "✅ Server is up and running successfully!"
                '''
                
                // Build documentation using the cached virtual environment binary
                sh 'export UV_CACHE_DIR="/var/jenkins_home/.uv_cache" && .venv/bin/python3 -m mkdocs build'
            }
        }
    }
    
    post {
        success {
            echo "All workloads finished successfully!"
        }
        failure {
            echo "Pipeline failed. Check the logs for errors."
        }
    }
}