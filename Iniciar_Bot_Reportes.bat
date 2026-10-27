@echo off
chcp 65001 > nul
title Consola de Control - Bot Reportes Itacamba
cd /d "%~dp0"
echo ======================================================================
echo   ITACAMBA CEMENTO S.A. - CONSOLA DE REPORTES Y BI
echo   Iniciando interfaz grafica de control...
echo ======================================================================

if exist venv\Scripts\python.exe (
    venv\Scripts\python.exe run_gui.py
) else (
    python run_gui.py
)

if errorlevel 1 (
    echo.
    echo [ERROR] No se pudo iniciar la interfaz. Revisa que las dependencias esten instaladas.
    pause
)
