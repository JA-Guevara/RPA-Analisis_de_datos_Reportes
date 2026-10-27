@echo off
chcp 65001 > nul
title Bot Reportes Itacamba - Ejecución Automática
cd /d "%~dp0"
echo ======================================================================
echo   ITACAMBA CEMENTO S.A. - EJECUTANDO PIPELINE COMPLETO Y EXPORTACIONES
echo ======================================================================
echo.

if exist venv\Scripts\python.exe (
    venv\Scripts\python.exe main.py
) else (
    python main.py
)

if errorlevel 1 (
    echo.
    echo ======================================================================
    echo [ERROR] Ocurrió un error durante la ejecución del pipeline.
    echo ======================================================================
    pause
) else (
    echo.
    echo ======================================================================
    echo [OK] Proceso completado exitosamente. Archivos exportados en reports.
    echo ======================================================================
    timeout /t 5
)
