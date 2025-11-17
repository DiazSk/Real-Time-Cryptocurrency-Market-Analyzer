# Week 8 Day 4-5 - Redis Pub/Sub Testing Script
# Tests event-driven WebSocket with Redis Pub/Sub

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Week 8 Day 4-5 - Redis Pub/Sub Tests" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

$baseUrl = "http://localhost:8000"
$testsPassed = 0
$testsFailed = 0

function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Url
    )
    
    Write-Host "[TEST] $Name..." -ForegroundColor Yellow -NoNewline
    
    try {
        $response = Invoke-WebRequest -Uri $Url -Method GET -ErrorAction Stop
        Write-Host " PASS" -ForegroundColor Green
        $script:testsPassed++
        return $response
    } catch {
        Write-Host " FAIL ($($_.Exception.Message))" -ForegroundColor Red
        $script:testsFailed++
        return $null
    }
}

# Test 1: API Health Check
Write-Host ""
Write-Host "=== API Health Check ===" -ForegroundColor Magenta
$response = Test-Endpoint "API Health" "$baseUrl/health"

# Test 2: WebSocket Test Page (Verifies WebSocket Router is Loaded)
Write-Host ""
Write-Host "=== WebSocket Test Page ===" -ForegroundColor Magenta
$response = Test-Endpoint "Test Page" "$baseUrl/ws/test"

if ($response) {
    Write-Host "  WebSocket router is loaded and functional" -ForegroundColor Green
    $script:testsPassed++
}

# Test 3: Check Flink Job Status
Write-Host ""
Write-Host "=== Flink Job Status ===" -ForegroundColor Magenta
Write-Host "[CHECK] Checking if Flink job is running..." -ForegroundColor Yellow -NoNewline

try {
    $flinkJobs = docker exec flink-jobmanager flink list 2>&1
    
    if ($flinkJobs -match "RUNNING") {
        Write-Host " RUNNING" -ForegroundColor Green
        $script:testsPassed++
        
        # Show job name
        $jobLine = $flinkJobs | Select-String "RUNNING" | Select-Object -First 1
        Write-Host "  Job: $jobLine" -ForegroundColor Cyan
    } else {
        Write-Host " NOT RUNNING" -ForegroundColor Red
        $script:testsFailed++
    }
} catch {
    Write-Host " FAIL (Cannot connect to Flink)" -ForegroundColor Red
    $script:testsFailed++
}

# Test 4: Check Redis Connection
Write-Host ""
Write-Host "=== Redis Connection ===" -ForegroundColor Magenta
Write-Host "[CHECK] Testing Redis connection..." -ForegroundColor Yellow -NoNewline

try {
    $redisPing = docker exec redis redis-cli PING 2>&1
    
    if ($redisPing -eq "PONG") {
        Write-Host " PONG" -ForegroundColor Green
        $script:testsPassed++
    } else {
        Write-Host " FAIL" -ForegroundColor Red
        $script:testsFailed++
    }
} catch {
    Write-Host " FAIL (Cannot connect to Redis)" -ForegroundColor Red
    $script:testsFailed++
}

# Test 5: Check for Recent Data
Write-Host ""
Write-Host "=== Recent Price Data ===" -ForegroundColor Magenta

$symbols = @("BTC", "ETH")
foreach ($symbol in $symbols) {
    Write-Host "[CHECK] Checking Redis cache for $symbol..." -ForegroundColor Yellow -NoNewline
    
    try {
        $key = "crypto:${symbol}:latest"
        $exists = docker exec redis redis-cli EXISTS $key 2>&1
        
        if ($exists -eq "1") {
            Write-Host " EXISTS" -ForegroundColor Green
            $script:testsPassed++
            
            # Check TTL
            $ttl = docker exec redis redis-cli TTL $key 2>&1
            Write-Host "  TTL: $ttl seconds" -ForegroundColor Cyan
        } else {
            Write-Host " NOT FOUND" -ForegroundColor Red
            $script:testsFailed++
        }
    } catch {
        Write-Host " FAIL" -ForegroundColor Red
        $script:testsFailed++
    }
}

# Manual Test Instructions
Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Manual Tests (Please Verify)" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "1. Test Redis Pub/Sub Manually:" -ForegroundColor Yellow
Write-Host "   Run in separate terminal:" -ForegroundColor Cyan
Write-Host "   docker exec -it redis redis-cli" -ForegroundColor White
Write-Host "   SUBSCRIBE crypto:updates" -ForegroundColor White
Write-Host "   (Wait 2 minutes for messages)" -ForegroundColor Gray
Write-Host ""

Write-Host "2. Test WebSocket Connection:" -ForegroundColor Yellow
Write-Host "   Open in browser:" -ForegroundColor Cyan
Write-Host "   http://localhost:8000/ws/test" -ForegroundColor White
Write-Host "   Click 'Connect BTC' and watch for real-time updates" -ForegroundColor Gray
Write-Host ""

Write-Host "3. Verify Flink is Publishing:" -ForegroundColor Yellow
Write-Host "   Run:" -ForegroundColor Cyan
Write-Host "   docker logs flink-taskmanager | findstr 'publish'" -ForegroundColor White
Write-Host "   Look for: 'Published BTC candle to X subscribers'" -ForegroundColor Gray
Write-Host ""

# Summary
Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Automated Test Summary" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Tests Passed: $testsPassed" -ForegroundColor Green
Write-Host "Tests Failed: $testsFailed" -ForegroundColor Red
Write-Host ""

$totalTests = $testsPassed + $testsFailed
if ($totalTests -gt 0) {
    $passRate = [math]::Round(($testsPassed / $totalTests) * 100, 1)
    Write-Host "Pass Rate: $passRate%" -ForegroundColor $(if ($passRate -ge 90) { "Green" } elseif ($passRate -ge 70) { "Yellow" } else { "Red" })
}

Write-Host ""

if ($testsFailed -eq 0) {
    Write-Host "All automated tests PASSED!" -ForegroundColor Green
    Write-Host "Now run the manual tests above to verify Pub/Sub is working." -ForegroundColor Yellow
} else {
    Write-Host "Some tests failed. Check the issues above." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "1. If Flink job not running: .\REDEPLOY_FLINK_PUBSUB.bat" -ForegroundColor White
Write-Host "2. If API not started: START_API.bat" -ForegroundColor White
Write-Host "3. If data missing: START_PRODUCER.bat (wait 2 min)" -ForegroundColor White
Write-Host ""
