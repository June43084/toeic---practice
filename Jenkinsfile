pipeline {
    agent any
    environment {
        DOCKER_IMAGE = 'gcr.io/toeic-memorize/toeic-memorize-app'
        DOCKER_TAG = "${env.BUILD_NUMBER}"
        CLOUD_RUN_SERVICE = 'toeic-memorize-app'
        CLOUD_RUN_REGION = 'us-central1'
        ALLURE_REPORT_URL = 'https://june43084.github.io/allure-reports-new'
    }
    stages {
        stage('Checkout') {
            steps {
                git credentialsId: 'github-token', url: 'https://github.com/June43084/myPytest-toeic-practice.git', branch: 'main'
            }
        }
        stage('Run Tests') {
            steps {
                bat "if exist allure-results rmdir /s /q allure-results"
                bat "if exist allure-report rmdir /s /q allure-report"
                bat "pip install allure-pytest"
                bat "pytest --alluredir=allure-results || exit 0"
            }
        }
        stage('Generate Allure Report') {
            steps {
                bat "allure generate allure-results -o allure-report"
            }
        }
        stage('Publish Allure Report') {
            steps {
                withCredentials([string(credentialsId: 'allure-reports-new', variable: 'ALLURE_TOKEN')]) {
                    bat '''
                        if exist allure-reports-tmp rmdir /s /q allure-reports-tmp
                        git clone -b main https://github.com/June43084/allure-reports-new.git allure-reports-tmp
                        cd allure-reports-tmp
                        del /Q *.* || exit 0
                        for /d %%i in (*) do if not "%%i"==".git" rmdir /s /q "%%i"
                        xcopy ..\\allure-report\\* . /E /Y /Q
                        git config user.name "Jenkins Bot"
                        git config user.email "jenkins@bot.com"
                        git add .
                        git commit -m "Update Allure report from build %BUILD_NUMBER%" || exit 0
                        git push https://%ALLURE_TOKEN%@github.com/June43084/allure-reports-new.git main
                    '''
                }
            }
        }
        stage('Build and Push Docker Image') {
            steps {
                withCredentials([file(credentialsId: 'firebase-admin-key', variable: 'FIREBASE_CRED_FILE')]) {
                    bat 'copy "%FIREBASE_CRED_FILE%" firebase-adminsdk.json || exit /b 1'
                    bat 'gcloud auth configure-docker || exit /b 1'
                    script {
                        def buildOutput = bat(script: 'gcloud builds submit --tag "%DOCKER_IMAGE%:%DOCKER_TAG%" --verbosity=info > build_output.txt 2>&1', returnStatus: true)
                        if (buildOutput != 0) {
                            error "Docker build failed: ${readFile('build_output.txt').trim()}"
                        }
                        bat 'del build_output.txt'
                        def gcrOutput = bat(script: 'gcloud container images describe %DOCKER_IMAGE%:%DOCKER_TAG% --format="value(image_summary.digest)" > gcr_output.txt 2>&1', returnStatus: true)
                        def gcrDigest = null
                        if (gcrOutput == 0) {
                            def output = readFile('gcr_output.txt').trim()
                            def matcher = output =~ /sha256:[0-9a-f]{64}/
                            if (matcher) {
                                gcrDigest = matcher[0]
                            }
                        }
                        bat 'del gcr_output.txt'
                        def imageDigestValue = gcrDigest ? "${DOCKER_IMAGE}@${gcrDigest}" : "${DOCKER_IMAGE}:${DOCKER_TAG}"
                        echo "Using image: ${imageDigestValue}"
                        writeFile file: 'image_digest_value.txt', text: imageDigestValue
                        if (!imageDigestValue.startsWith('gcr.io/')) {
                            error "Invalid image digest: ${imageDigestValue}"
                        }
                    }
                }
            }
        }
        stage('Deploy to Cloud Run') {
            steps {
                withCredentials([file(credentialsId: 'google-cloud-credentials', variable: 'GOOGLE_APPLICATION_CREDENTIALS')]) {
                    bat 'gcloud auth activate-service-account --key-file="%GOOGLE_APPLICATION_CREDENTIALS%" || exit /b 1'
                    script {
                        def imageToDeploy = readFile('image_digest_value.txt').trim()
                        bat "gcloud run deploy \"%CLOUD_RUN_SERVICE%\" --image \"${imageToDeploy}\" --region \"%CLOUD_RUN_REGION%\" --platform managed --allow-unauthenticated --set-env-vars \"FIREBASE_CREDENTIALS_PATH=/app/firebase-adminsdk.json\" || exit /b 1"
                    }
                    sleep 30
                }
            }
        }
        stage('Verify Deployment') {
            steps {
                withCredentials([file(credentialsId: 'google-cloud-credentials', variable: 'GOOGLE_APPLICATION_CREDENTIALS')]) {
                    bat 'gcloud auth activate-service-account --key-file="%GOOGLE_APPLICATION_CREDENTIALS%" || exit /b 1'
                    script {
                        def expectedImage = readFile('image_digest_value.txt').trim()
                        retry(3) {
                            bat 'cmd /c gcloud run revisions list --service="%CLOUD_RUN_SERVICE%" --region="%CLOUD_RUN_REGION%" --limit=1 --format="value(spec.containers[0].image)" > temp_output.txt'
                            def deployedImage = readFile('temp_output.txt').trim()
                            bat 'del temp_output.txt'
                            if (deployedImage.startsWith("gcr.io/") && (deployedImage == expectedImage || deployedImage == "${DOCKER_IMAGE}:${DOCKER_TAG}")) {
                                echo "✔️ Deployment verified: ${deployedImage}"
                                return
                            }
                            sleep 10
                            error "Invalid or mismatched image: ${deployedImage}"
                        }
                    }
                }
            }
        }
    }
    post {
        always {
            script {
                def summary = [statistic: [passed: 0, failed: 0, skipped: 0]]
                try {
                    def summaryFile = "${WORKSPACE}/allure-report/widgets/summary.json"
                    if (fileExists(summaryFile)) {
                        summary = readJSON file: summaryFile
                    }
                } catch (Exception e) {
                    echo "Warning: Unable to read Allure summary: ${e.message}"
                }
                def buildStatus = (summary.statistic.failed > 0 || currentBuild.result == 'FAILURE') ? 'FAILURE' : 'SUCCESS'
                emailext to: 'zzz61407@gmail.com',
                    subject: "${env.JOB_NAME} #${env.BUILD_NUMBER} - ${buildStatus}",
                    body: "${buildStatus}: ${env.JOB_NAME} #${env.BUILD_NUMBER}\n\n" +
                          "Tests Passed: ${summary.statistic.passed}\n" +
                          "Tests Failed: ${summary.statistic.failed}\n" +
                          "Tests Skipped: ${summary.statistic.skipped}\n\n" +
                          "Build Log: ${env.BUILD_URL}\n" +
                          "Allure Report: ${summary.statistic.passed > 0 ? env.ALLURE_REPORT_URL : 'No report generated'}",
                    mimeType: 'text/plain',
                    attachLog: true
            }
        }
    }
}
