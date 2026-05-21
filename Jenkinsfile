pipeline {
    agent any

    environment {
        // Ensures Python output is sent straight to the terminal without buffering
        PYTHONUNBUFFERED = '1'
    }

    stages {
        // ==========================================
        // 0. ENVIRONMENT SETUP
        // ==========================================
        stage('Setup Python Venv') {
            steps {
                echo 'Creating Python Virtual Environment...'
                sh '''
                    # use Python 3.10 from your custom image
                    python3 -m venv venv
                    ./venv/bin/pip install --upgrade pip setuptools wheel
                    ./venv/bin/pip install --no-cache-dir -r requirements.txt
                '''
            }
        }

        // =========================================
        // 1. WORKLOADS WORKFLOW (Pull Request)
        // =========================================
        stage('Model Development Workloads') {
            when {
                changeRequest target: 'main'
            }
            steps {
                echo "Pull Request detected. Running model development workloads..."
                
                // Change into the madewithml directory before running scripts
                // Notice the virtual env path uses '../' to go up one level
                dir('madewithml') {
                    sh '../venv/bin/python train.py'
                    sh '../venv/bin/python evaluate.py'
                }
            }
        }

        // ==========================================
        // 2. SERVE & DOCS WORKFLOW (Push to main)
        // ==========================================
        stage('Deploy and Document') {
            when {
                branch 'main'
                not { changeRequest() } 
            }
            steps {
                echo "Push to main detected. Deploying application and updating docs..."
                
                // Run the serving script from inside its directory
                dir('madewithml') {
                    sh '../venv/bin/python serve.py'
                }
                
                // Update documentation 
                // mkdocs is executed from the root where mkdocs.yml typically lives
                sh './venv/bin/mkdocs build'
            }
        }
    }
    
    post {
        always {
            // Clean up the virtual environment so it doesn't take up disk space
            sh 'rm -rf venv'
            echo "Pipeline execution complete. Cleaned up workspace."
        }
        success {
            echo "All workloads finished successfully!"
        }
        failure {
            echo "Pipeline failed. Check the logs for errors."
        }
    }
}