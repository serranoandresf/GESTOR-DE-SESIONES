@echo off
REM Abre el Gestor de Sesiones sin ventana de consola (requiere Python 3.10+ instalado).
cd /d "%~dp0"
start "" pyw -3 main.py
