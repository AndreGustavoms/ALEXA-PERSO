Option Explicit

Dim shell, fileSystem, processEnvironment, projectDirectory, pythonwPath, venvPythonPath
Dim runtimePath, modelPath, buildPath, runtimeCommand, configPath, configFile, configLine, basePythonHome, candidatePythonw
Dim updateScript, updateCommand

Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")

projectDirectory = fileSystem.GetParentFolderName(WScript.ScriptFullName)
updateScript = fileSystem.BuildPath(projectDirectory, "scripts\update-assistant.ps1")

If fileSystem.FileExists(updateScript) Then
  updateCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File " & Chr(34) & updateScript & Chr(34) & " -Silent"
  shell.Run updateCommand, 0, True
End If

pythonwPath = fileSystem.BuildPath(projectDirectory, ".venv\Scripts\pythonw.exe")
venvPythonPath = fileSystem.BuildPath(projectDirectory, ".venv\Scripts\python.exe")
runtimePath = fileSystem.BuildPath(projectDirectory, "assistant_runtime\main.py")
modelPath = fileSystem.BuildPath(projectDirectory, "runtime\models\vosk-model-small-pt-0.3")
buildPath = fileSystem.BuildPath(projectDirectory, "dist\index.html")
configPath = fileSystem.BuildPath(projectDirectory, ".venv\pyvenv.cfg")

If Not fileSystem.FileExists(pythonwPath) Or _
   Not fileSystem.FolderExists(modelPath) Or _
   Not fileSystem.FileExists(buildPath) Then
  shell.Run Chr(34) & fileSystem.BuildPath(projectDirectory, "INSTALAR_ASSISTENTE.cmd") & Chr(34), 1, False
  WScript.Quit
End If

' O executavel do venv e um redirecionador no Windows. Usar o Python base com
' __PYVENV_LAUNCHER__ preserva o ambiente e evita um processo intermediario.
If fileSystem.FileExists(configPath) Then
  Set configFile = fileSystem.OpenTextFile(configPath, 1, False)
  Do Until configFile.AtEndOfStream
    configLine = Trim(configFile.ReadLine)
    If LCase(Left(configLine, 7)) = "home = " Then
      basePythonHome = Trim(Mid(configLine, 8))
      Exit Do
    End If
  Loop
  configFile.Close

  If Len(basePythonHome) > 0 Then
    candidatePythonw = fileSystem.BuildPath(basePythonHome, "pythonw.exe")
    If fileSystem.FileExists(candidatePythonw) Then
      pythonwPath = candidatePythonw
      Set processEnvironment = shell.Environment("Process")
      processEnvironment("__PYVENV_LAUNCHER__") = venvPythonPath
    End If
  End If
End If

shell.CurrentDirectory = projectDirectory
runtimeCommand = Chr(34) & pythonwPath & Chr(34) & " " & Chr(34) & runtimePath & Chr(34)

If WScript.Arguments.Count > 0 Then
  If LCase(WScript.Arguments(0)) = "open" Then
    runtimeCommand = runtimeCommand & " --open"
  End If
End If

shell.Run runtimeCommand, 0, False
