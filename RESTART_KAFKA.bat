@echo off
REM ==========================================
REM   Kafka Restart Helper Script
REM ==========================================
REM
REM This script fixes the common Kafka startup issue:
REM "KeeperException$NodeExistsException"
REM
REM Root Cause: Kafka didn't shut down cleanly and
REM left stale registrations in ZooKeeper
REM
REM Solution: Clean restart of Kafka + ZooKeeper
REM ==========================================

echo.
echo ==========================================
echo   Restarting Kafka ^& ZooKeeper
echo ==========================================
echo.

echo [1/4] Stopping all containers...
docker-compose down

echo.
echo [2/4] Starting containers with fresh state...
docker-compose up -d

echo.
echo [3/4] Waiting for Kafka to become healthy (30s)...
timeout /t 30 /nobreak >nul

echo.
echo [4/4] Verifying Kafka status...
docker ps | findstr "kafka"

echo.
echo ==========================================
echo   Kafka Restart Complete!
echo ==========================================
echo.
echo Check Kafka health: docker ps | findstr kafka
echo View Kafka logs:    docker logs kafka
echo Kafka UI:          http://localhost:8081
echo.

pause
