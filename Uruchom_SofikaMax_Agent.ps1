# SofikaMax Agent - cichy start Dashboardu (bez okien)
# Uzyj jesli .vbs zglasza blad. Dwuklik lub: powershell -ExecutionPolicy Bypass -File "Uruchom_SofikaMax_Agent.ps1"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $dir
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "pythonw.exe"
$psi.Arguments = "start_dashboard_only.py"
$psi.WorkingDirectory = $dir
$psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
$psi.UseShellExecute = $false
[System.Diagnostics.Process]::Start($psi) | Out-Null
