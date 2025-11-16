# Start FastAPI in background
$jobScript = {
    Set-Location "C:\Real-Time-Cryptocurrency-Market-Analyzer"
    & ".\venv\Scripts\activate.ps1"
    uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
}

Start-Job -ScriptBlock $jobScript -Name "FastAPI-Server"
Write-Host "✅ FastAPI server started in background"
Write-Host "📡 API running at: http://localhost:8000"
Write-Host "📚 API docs: http://localhost:8000/docs"
Write-Host ""
Write-Host "To check status: Get-Job -Name 'FastAPI-Server'"
Write-Host "To view logs: Receive-Job -Name 'FastAPI-Server' -Keep"
Write-Host "To stop: Stop-Job -Name 'FastAPI-Server'; Remove-Job -Name 'FastAPI-Server'"
