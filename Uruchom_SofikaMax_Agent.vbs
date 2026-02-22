Option Explicit
Dim sh, fso, scriptDir
Set sh = WScript.CreateObject("WScript.Shell")
Set fso = WScript.CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
sh.Run "cmd /c cd /d """ & scriptDir & """ && pythonw start_dashboard_only.py", 0, False
