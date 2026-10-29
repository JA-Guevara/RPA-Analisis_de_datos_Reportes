@echo off
chcp 65001 > nul
title Probar Conexion y Descarga SAP - Bot Reportes Itacamba
cd /d "%~dp0"
echo ======================================================================
echo   ITACAMBA CEMENTO S.A. - DIAGNOSTICO Y PRUEBA DE DESCARGA SAP GUI
echo ======================================================================
echo.

if exist venv\Scripts\python.exe (
    venv\Scripts\python.exe scripts\test_sap.py %*
) else (
    python scripts\test_sap.py %*
)

echo.
pause
