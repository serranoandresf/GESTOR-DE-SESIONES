@echo off
REM Quita la app, los accesos directos y su registro en Windows. NO borra tus datos (proyectos, grupos, contrasenas).
set "APP=%~dp0"
if "%APP:~-1%"=="\" set "APP=%APP:~0,-1%"
powershell -NoProfile -Command "foreach($d in @([Environment]::GetFolderPath('Desktop'),[Environment]::GetFolderPath('Programs'))){ Remove-Item -LiteralPath (Join-Path $d 'Gestor de Sesiones.lnk') -ErrorAction SilentlyContinue }"
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\GestorSesiones" /f >nul 2>&1
echo Gestor de Sesiones desinstalado. Tus datos no se borraron.
(goto) 2>nul & rmdir /s /q "%APP%"
