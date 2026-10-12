@echo off
REM Genera un unico .exe con icono (dist\GestorSesiones.exe) con PyInstaller. Requiere Python 3.10+ e internet SOLO para instalar PyInstaller.
cd /d "%~dp0"
py -3 -m pip install --upgrade pyinstaller
py -3 -m PyInstaller --noconsole --onefile --name GestorSesiones --icon gestor_sesiones\recursos\icono.ico --add-data "gestor_sesiones\recursos;gestor_sesiones\recursos" main.py
echo.
echo Listo. Tu programa esta en: %~dp0dist\GestorSesiones.exe
pause
