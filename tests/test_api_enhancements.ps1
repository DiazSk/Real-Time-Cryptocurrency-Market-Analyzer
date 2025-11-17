# Week 8 Day 3 - API Enhancement Testing Script
# Tests pagination, ordering, headers, stats, and bulk endpoints

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Week 8 Day 3 - API Enhancement Tests" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$baseUrl = "http://localhost:8000"
$testsPassed = 0
$testsFailed = 0

function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Url,
        [string]$ExpectedStatus = "200"
    )
    
    Write-Host "[TEST] $Name..." -ForegroundColor Yellow -NoNewline
    
    try {
        $response = Invoke-WebRequest -Uri $Url -Method GET -ErrorAction Stop
        
        if ($response.StatusCode -eq $ExpectedStatus) {
            Write-Host " ✅ PASS" -ForegroundColor Green
            $script:testsPassed++
            return $response
        } else {
            Write-Host " ❌ FAIL (Status: $($response.StatusCode))" -ForegroundColor Red
            $script:testsFailed++
            return $null
        }
    } catch {
        Write-Host " ❌ FAIL ($($_.Exception.Message))" -ForegroundColor Red
        $script:testsFailed++
        return $null
    }
}

function Test-Header {
    param(
        [string]$Name,
        [object]$Response,
        [string]$HeaderName
    )
    
    Write-Host "  [CHECK] Header: $HeaderName..." -ForegroundColor Cyan -NoNewline
    
    if ($Response.Headers[$HeaderName]) {
        Write-Host " ✅ Found: $($Response.Headers[$HeaderName])" -ForegroundColor Green
        return $true
    } else {
        Write-Host " ❌ Missing" -ForegroundColor Red
        return $false
    }
}

# Test 1: Health Check
Write-Host ""
Write-Host "=== Basic Health Check ===" -ForegroundColor Magenta
$response = Test-Endpoint "Health Check" "$baseUrl/health"

# Test 2: Latest Endpoints with Headers
Write-Host ""
Write-Host "=== Latest Price Endpoints ===" -ForegroundColor Magenta

$response = Test-Endpoint "Latest BTC Price" "$baseUrl/api/v1/latest/BTC"
if ($response) {
    Test-Header "BTC Cache Headers" $response "X-Cache-Hit"
    Test-Header "BTC Query Time" $response "X-Query-Time-Ms"
    Test-Header "BTC Cache TTL" $response "X-Cache-TTL-Seconds"
    Test-Header "BTC Data Age" $response "X-Data-Age-Seconds"
}

$response = Test-Endpoint "Latest ETH Price" "$baseUrl/api/v1/latest/ETH"

$response = Test-Endpoint "Bulk Latest Prices" "$baseUrl/api/v1/latest/all"
if ($response) {
    Test-Header "Bulk Cache Hit Rate" $response "X-Cache-Hit-Rate"
    Test-Header "Bulk Total Symbols" $response "X-Total-Symbols"
}

# Test 3: Historical with Pagination
Write-Host ""
Write-Host "=== Historical Pagination ===" -ForegroundColor Magenta

$response = Test-Endpoint "Historical - Page 1" "$baseUrl/api/v1/historical/BTC?limit=10&offset=0"
if ($response) {
    Test-Header "Page 1 Total Count" $response "X-Total-Count"
    Test-Header "Page 1 Returned" $response "X-Returned-Count"
    Test-Header "Page 1 Has More" $response "X-Has-More"
}

$response = Test-Endpoint "Historical - Page 2" "$baseUrl/api/v1/historical/BTC?limit=10&offset=10"

# Test 4: Historical with Ordering
Write-Host ""
Write-Host "=== Historical Ordering ===" -ForegroundColor Magenta

$response = Test-Endpoint "Historical - DESC (newest first)" "$baseUrl/api/v1/historical/BTC?limit=5&order_by=desc"
$response = Test-Endpoint "Historical - ASC (oldest first)" "$baseUrl/api/v1/historical/BTC?limit=5&order_by=asc"

# Test 5: Stats Endpoint
Write-Host ""
Write-Host "=== Statistical Endpoints ===" -ForegroundColor Magenta

$response = Test-Endpoint "BTC Statistics" "$baseUrl/api/v1/historical/BTC/stats"
if ($response) {
    $stats = $response.Content | ConvertFrom-Json
    Write-Host "  📊 Lowest: $($stats.lowest_price)" -ForegroundColor Cyan
    Write-Host "  📊 Highest: $($stats.highest_price)" -ForegroundColor Cyan
    Write-Host "  📊 Average: $($stats.average_price)" -ForegroundColor Cyan
    Write-Host "  📊 Candles: $($stats.candle_count)" -ForegroundColor Cyan
}

$response = Test-Endpoint "ETH Statistics" "$baseUrl/api/v1/historical/ETH/stats"

# Test 6: Validation Errors
Write-Host ""
Write-Host "=== Validation Error Handling ===" -ForegroundColor Magenta

# This should fail with 422 (validation error)
Write-Host "[TEST] Invalid order_by parameter..." -ForegroundColor Yellow -NoNewline
try {
    $response = Invoke-WebRequest -Uri "$baseUrl/api/v1/historical/BTC?order_by=invalid" -Method GET -ErrorAction Stop
    Write-Host " ❌ FAIL (Should have failed)" -ForegroundColor Red
    $script:testsFailed++
} catch {
    if ($_.Exception.Response.StatusCode.value__ -eq 422) {
        Write-Host " ✅ PASS (Correctly rejected)" -ForegroundColor Green
        $script:testsPassed++
    } else {
        Write-Host " ❌ FAIL (Wrong status code)" -ForegroundColor Red
        $script:testsFailed++
    }
}

# Test 7: Performance Headers
Write-Host ""
Write-Host "=== Performance Headers ===" -ForegroundColor Magenta

$response = Test-Endpoint "Request with Process Time" "$baseUrl/api/v1/latest/BTC"
if ($response) {
    Test-Header "Process Time" $response "X-Process-Time-Ms"
    Test-Header "Request ID" $response "X-Request-ID"
}

# Test 8: Latest Historical (Bonus)
Write-Host ""
Write-Host "=== Latest Historical ===" -ForegroundColor Magenta

$response = Test-Endpoint "Latest BTC from DB" "$baseUrl/api/v1/historical/BTC/latest"
$response = Test-Endpoint "Latest ETH from DB" "$baseUrl/api/v1/historical/ETH/latest"

# Summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Test Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "✅ Tests Passed: $testsPassed" -ForegroundColor Green
Write-Host "❌ Tests Failed: $testsFailed" -ForegroundColor Red
Write-Host ""

$totalTests = $testsPassed + $testsFailed
$passRate = [math]::Round(($testsPassed / $totalTests) * 100, 1)

Write-Host "Pass Rate: $passRate%" -ForegroundColor $(if ($passRate -ge 90) { "Green" } elseif ($passRate -ge 70) { "Yellow" } else { "Red" })
Write-Host ""

if ($testsFailed -eq 0) {
    Write-Host "🎉 ALL TESTS PASSED! Week 8 Day 3 Complete!" -ForegroundColor Green
} else {
    Write-Host "⚠️  Some tests failed. Check API logs for details." -ForegroundColor Yellow
}

Write-Host ""
