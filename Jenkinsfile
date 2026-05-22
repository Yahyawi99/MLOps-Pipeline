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
    echo "Push to main detected. Translating requirements and deploying application..."

    sh '''
        # 1. DYNAMIC TRANSLATION: Strip legacy pins so pip can find Python 3.13 wheels
        python3 -c "
with open('requirements.txt', 'r') as f:
    lines = f.readlines()
with open('requirements_313.txt', 'w') as f:
    for line in lines:
        # Strip exact version pins (==)
        clean_line = line.split('==')[0].strip()
        # Modern Ray has dropped the legacy 'air' bundle; replace it with base ray
        if 'ray[air]' in clean_line:
            clean_line = 'ray'
        f.write(clean_line + '\n')
"

        echo "--- Generated Python 3.13 Compatible Requirements ---"
        cat requirements_313.txt
        echo "-----------------------------------------------------"

        # 2. Install the modern unpinned dependency stack
        python3 -m pip install --break-system-packages -r requirements_313.txt

        # 3. Explicitly force down your required CLI overrides and web extensions
        python3 -m pip install --break-system-packages "click<8.1.0" "typer==0.9.0" "ray[serve]"

        # 4. Tell Jenkins NOT to kill our background processes
        export JENKINS_NODE_COOKIE=dontKillMe
        
        # 5. Get the latest Model Run ID
        LATEST_RUN_ID=$(python3 -c "import mlflow; from madewithml.config import MLFLOW_TRACKING_URI; mlflow.set_tracking_uri(MLFLOW_TRACKING_URI); runs=mlflow.search_runs(experiment_names=['llm-classification']); print(runs.iloc[0].run_id if not runs.empty else '')")
        
        if [ -z "$LATEST_RUN_ID" ]; then
            echo "Error: No MLflow runs found. You must train a model first!"
            exit 1
        fi
        echo "Found Run ID: $LATEST_RUN_ID"
        
        # 6. Stop any existing deployed models
        ray stop || true
        
        # 7. Deploy the new model in the background and capture its Process ID (PID)
        nohup python3 madewithml/serve.py --run_id $LATEST_RUN_ID > serve.log 2>&1 &
        SERVE_PID=$!
        
        # 8. DIAGNOSTIC POLLING: Wait for server or catch early crash
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
