@echo off
chcp 65001 > nul
title Limpiar Base de Datos - Bot Reportes Itacamba
cd /d "%~dp0"
echo ======================================================================
echo   ITACAMBA CEMENTO S.A. - LIMPIEZA DE BASE DE DATOS SQL SERVER
echo ======================================================================
echo.

if exist venv\Scripts\python.exe (
    venv\Scripts\python.exe scripts\limpiar_bd.py %*
) else (
    python scripts\limpiar_bd.py %*
)

echo.
pause
