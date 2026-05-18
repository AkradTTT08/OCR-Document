@echo off
title Thai OCR Spell Check



:: ── Start Flask backend ──
echo [1/2] Starting Flask backend on port 5000...
start "Flask Backend" cmd /k "cd /d %~dp0 && python backend\app.py"

timeout /t 2 /nobreak > nul

:: ── Start Svelte dev server ──
echo [2/2] Starting Svelte frontend on port 5173...
start "Svelte Frontend" cmd /k "cd /d %~dp0svelte-app && npm run dev"

timeout /t 3 /nobreak > nul

:: ── Open browser ──
echo Opening browser...
start http://localhost:5173

echo.
echo ════════════════════════════════════════
echo  Flask API : http://localhost:5000
echo  Web App   : http://localhost:5173
echo ════════════════════════════════════════
