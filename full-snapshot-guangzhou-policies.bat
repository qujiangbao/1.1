@echo off
chcp 65001 >nul
title Guangzhou Policy Full Snapshot
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0full-snapshot-guangzhou-policies.ps1"
if errorlevel 1 (
  echo.
  echo Full snapshot failed.
  pause
)

