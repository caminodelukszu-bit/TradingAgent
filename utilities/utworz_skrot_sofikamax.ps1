# Tworzy skrot "Uruchom SofikaMax Agent" z ikona logo SofikaMax.
# Uruchom: powershell -ExecutionPolicy Bypass -File "utilities\utworz_skrot_sofikamax.ps1"
# Skrot powstaje w folderze projektu; mozesz go skopiowac na pulpit (wtedy ikona bedzie widoczna).

$dir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ico = Join-Path $dir "assets\sofikamax_logo.ico"
$vbs = Join-Path $dir "Uruchom_SofikaMax_Agent.vbs"
$wsh = New-Object -ComObject WScript.Shell
# Skrot w folderze projektu (mozna potem przeciagnac na pulpit)
$shortcutPath = Join-Path $dir "Uruchom SofikaMax Agent.lnk"
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "wscript.exe"
$shortcut.Arguments = "`"$vbs`""
$shortcut.WorkingDirectory = $dir
$shortcut.WindowStyle = 7
if (Test-Path $ico) {
    $shortcut.IconLocation = "$ico,0"
}
$shortcut.Description = "SofikaMax Agent - Dashboard"
$shortcut.Save()
Write-Host "Skrot z ikona SofikaMax: $shortcutPath"
Write-Host "Przeciagnij ten plik .lnk na pulpit, zeby miec logo przy uruchamianiu."
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($wsh) | Out-Null
