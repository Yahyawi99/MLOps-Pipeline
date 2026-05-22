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
    echo "Push to main detected. Installing explicit dependencies and deploying application..."

    sh '''
        # 1. Clean install of all required application, serving, and documentation dependencies
        python3 -m pip install --break-system-packages \
            "click<8.1.0" \
            "typer==0.9.0" \
            "ray[serve]" \
            mlflow \
            numpy \
            numpyencoder \
            pandas \
            torch \
            transformers \
            snorkel \
            scikit-learn \
            hyperopt \
            nltk \
            python-dotenv \
            SQLAlchemy \
            fastapi \
            mkdocs \
            mkdocstrings \
            "mkdocstrings[python]"

        # 2. Tell Jenkins NOT to kill our background processes
        export JENKINS_NODE_COOKIE=dontKillMe
        
        # 3. Get the latest Model Run ID
        LATEST_RUN_ID=$(python3 -c "import mlflow; from madewithml.config import MLFLOW_TRACKING_URI; mlflow.set_tracking_uri(MLFLOW_TRACKING_URI); runs=mlflow.search_runs(experiment_names=['llm-classification']); print(runs.iloc[0].run_id if not runs.empty else '')")
        
        if [ -z "$LATEST_RUN_ID" ]; then
            echo "Error: No MLflow runs found. You must train a model first!"
            exit 1
        fi
        echo "Found Run ID: $LATEST_RUN_ID"
        
        # 4. Stop any existing deployed models
        ray stop || true
        
        # 5. Deploy the new model in the background and capture its Process ID (PID)
        nohup python3 madewithml/serve.py --run_id $LATEST_RUN_ID > serve.log 2>&1 &
        SERVE_PID=$!
        
        # 6. DIAGNOSTIC POLLING: Wait for server or catch early crash
        echo "Waiting for Ray Serve to initialize on port 8000..."
        TIMEOUT=120
        ELAPSED=0
        SLEEP_INTERVAL=2

        while ! curl -s -f http://127.0.0.1:8000/ > /dev/null; do
            # CRITICAL CHECK: Did the background process die?
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
    
    // Build the documentation
    sh 'python3 -m mkdocs build'
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
