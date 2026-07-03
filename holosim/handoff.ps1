# Improved HOLO PowerShell Handoff
$python = "python"
$cli = "D:\death\Holo-Invariant-main\holosim\holo_cli.py"

Write-Host "=== HOLO PowerShell Handoff ===" -ForegroundColor Green

& $python $cli boot

& $python $cli append "PowerShell screening flow executed. Delta filed at $(Get-Date). Continuity preserved."

& $python $cli health

Write-Host "Handoff complete. Check chain state with: python holo_cli.py state" -ForegroundColor Green