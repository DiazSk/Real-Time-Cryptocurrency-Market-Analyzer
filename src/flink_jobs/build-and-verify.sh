#!/bin/bash

# Flink Job Build and Verification Script
# Automates the build and basic validation process

echo "==================================="
echo "Flink Job Build & Verification"
echo "==================================="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Check Java
echo "Step 1: Checking Java..."
if command -v java &> /dev/null; then
    JAVA_VERSION=$(java -version 2>&1 | head -n 1)
    echo -e "${GREEN}✓ Java found: $JAVA_VERSION${NC}"
else
    echo -e "${RED}✗ Java not found. Please install Java 21.${NC}"
    exit 1
fi

# Step 2: Check Maven
echo ""
echo "Step 2: Checking Maven..."
if command -v mvn &> /dev/null; then
    MVN_VERSION=$(mvn -version | head -n 1)
    echo -e "${GREEN}✓ Maven found: $MVN_VERSION${NC}"
else
    echo -e "${RED}✗ Maven not found. Please install Maven.${NC}"
    exit 1
fi

# Step 3: Check Docker containers
echo ""
echo "Step 3: Checking Docker containers..."
FLINK_JM=$(docker ps --filter "name=flink-jobmanager" --format "{{.Status}}")
KAFKA=$(docker ps --filter "name=kafka" --format "{{.Status}}")

if [[ $FLINK_JM == *"Up"* ]]; then
    echo -e "${GREEN}✓ Flink JobManager is running${NC}"
else
    echo -e "${RED}✗ Flink JobManager is not running. Start docker-compose.${NC}"
    exit 1
fi

if [[ $KAFKA == *"Up"* ]]; then
    echo -e "${GREEN}✓ Kafka is running${NC}"
else
    echo -e "${RED}✗ Kafka is not running. Start docker-compose.${NC}"
    exit 1
fi

# Step 4: Build Maven project
echo ""
echo "Step 4: Building Maven project..."
mvn clean package -DskipTests

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Build successful!${NC}"
else
    echo -e "${RED}✗ Build failed. Check logs above.${NC}"
    exit 1
fi

# Step 5: Check JAR file
echo ""
echo "Step 5: Verifying JAR file..."
if [ -f "target/crypto-analyzer-flink-1.0.0.jar" ]; then
    JAR_SIZE=$(du -h target/crypto-analyzer-flink-1.0.0.jar | cut -f1)
    echo -e "${GREEN}✓ JAR file created: $JAR_SIZE${NC}"
else
    echo -e "${RED}✗ JAR file not found in target/.${NC}"
    exit 1
fi

# Step 6: Copy JAR to Flink container
echo ""
echo "Step 6: Copying JAR to Flink container..."
docker cp target/crypto-analyzer-flink-1.0.0.jar flink-jobmanager:/opt/flink/

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ JAR copied to Flink container${NC}"
else
    echo -e "${RED}✗ Failed to copy JAR. Check Docker.${NC}"
    exit 1
fi

# Summary
echo ""
echo "==================================="
echo -e "${GREEN}✓ All checks passed!${NC}"
echo "==================================="
echo ""
echo "Next steps:"
echo "1. Submit job: docker exec flink-jobmanager flink run /opt/flink/crypto-analyzer-flink-1.0.0.jar"
echo "2. View logs: docker logs -f flink-taskmanager"
echo "3. Web UI: http://localhost:8082"
echo ""
