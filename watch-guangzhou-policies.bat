@echo off
chcp 65001 >nul
title Guangzhou Industrial Park Policy Sync
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0refresh-guangzhou-policies.ps1" -Watch
if errorlevel 1 (
  echo.
  echo Policy sync stopped because of an error.
  pause
)
