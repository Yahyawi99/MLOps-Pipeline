pipeline {
    agent any

    environment {
        PYTHONPATH = "${WORKSPACE}"
        MLFLOW_TRACKING_URI = "http://127.0.0.1:8080"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Setup Environment') {
            steps {
                sh '''
                    python3 -m venv .venv
                    .venv/bin/pip install --upgrade pip setuptools wheel
                    .venv/bin/pip install -r requirements.txt
                '''
            }
        }

        stage('Test Data & Code') {
            steps {
                sh '''
                    # Run data and code quality tests
                    .venv/bin/pytest tests/code --verbose --disable-warnings
                '''
            }
        }

        stage('Train Model') {
            steps {
                sh '''
                    # Train model using space-separated options to satisfy Typer
                    .venv/bin/python3 madewithml/train.py \
                        --experiment-name "llm-classification" \
                        --dataset-loc "$(pwd)/datasets/dataset.csv" \
                        --train-loop-config '{"dropout_p": 0.5, "lr": 1e-4, "lr_factor": 0.8, "lr_patience": 3, "num_epochs": 1, "batch_size": 2}' \
                        --num-samples 20 \
                        --num-workers 1 \
                        --cpu-per-worker 1 \
                        --gpu-per-worker 0
                '''
            }
        }

        stage('Evaluate Model') {
            steps {
                sh '''
                    # Retrieve the latest run ID from MLflow to evaluate
                    RUN_ID=$(.venv/bin/python3 -c "
import mlflow
client = mlflow.tracking.MlflowClient()
experiment = client.get_experiment_by_name('llm-classification')
runs = client.search_runs(experiment_ids=[experiment.experiment_id], order_by=['attributes.start_time DESC'], max_results=1)
if runs: print(runs[0].info.run_id)
")
                    
                    if [ -z "$RUN_ID" ]; then
                        echo "No active MLflow run found for evaluation."
                        exit 1
                    fi

                    echo "Evaluating Run ID: $RUN_ID"
                    .venv/bin/python3 madewithml/evaluate.py --run-id "$RUN_ID"
                    .venv/bin/pytest --run-id="$RUN_ID" tests/model --verbose --disable-warnings
                '''
            }
        }

        stage('Deploy and Document') {
            steps {
                echo "Model training and evaluation successful. Ready for deployment steps."
                # Add serving / registry rollout logic here if needed
            }
        }
    }

    post {
        always {
            echo "Pipeline finished."
        }
        success {
            echo "Pipeline completed successfully!"
        }
        failure {
            echo "Pipeline failed. Check the logs for errors."
        }
    }
}