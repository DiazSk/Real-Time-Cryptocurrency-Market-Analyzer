@echo off
REM ============================================
REM Flink Job Rebuild and Redeploy Script
REM Week 8 Day 4-5: Redis Pub/Sub Enhancement
REM ============================================

echo.
echo ========================================
echo   Rebuilding Flink Job with Pub/Sub
echo ========================================
echo.

REM Change to Flink jobs directory
cd /d "%~dp0src\flink_jobs"

echo [INFO] Building Maven project...
call mvn clean package -DskipTests

if errorlevel 1 (
    echo.
    echo [ERROR] Maven build failed!
    pause
    exit /b 1
)

echo.
echo [INFO] Build successful!
echo.

REM Get current running job
echo [INFO] Checking for running Flink jobs...
docker exec flink-jobmanager flink list > temp_jobs.txt

REM Extract job ID if exists
for /f "tokens=5" %%i in ('findstr /C:"RUNNING" temp_jobs.txt') do (
    set JOB_ID=%%i
    goto :found
)

:found
if defined JOB_ID (
    echo [INFO] Found running job: %JOB_ID%
    echo [INFO] Cancelling job...
    docker exec flink-jobmanager flink cancel %JOB_ID%
    timeout /t 5
) else (
    echo [INFO] No running job found
)

del temp_jobs.txt

REM Copy new JAR to Flink
echo.
echo [INFO] Copying JAR to Flink JobManager...
docker cp target\crypto-analyzer-flink-1.0.0.jar flink-jobmanager:/opt/flink/

REM Deploy new job
echo.
echo [INFO] Deploying enhanced job with Redis Pub/Sub...
docker exec flink-jobmanager flink run -d /opt/flink/crypto-analyzer-flink-1.0.0.jar

echo.
echo [INFO] Waiting for job to start...
timeout /t 10

REM Verify job is running
echo.
echo [INFO] Checking job status...
docker exec flink-jobmanager flink list

echo.
echo ========================================
echo   Deployment Complete!
echo ========================================
echo.
echo [INFO] Check Flink Web UI: http://localhost:8082
echo [INFO] Monitor TaskManager logs: docker logs -f flink-taskmanager
echo.

pause
