@echo off
title Sales Jar Tracker
echo.
echo  =========================================
echo   Sales Jar Tracker - Starting...
echo  =========================================
echo.

:: Change to the app folder (same folder as this bat file)
cd /d "%~dp0app"

:: Open browser then start the Flask server
echo  Starting server at http://localhost:5050
echo  Press Ctrl+C to stop the server.
echo.
start "" "http://localhost:5050"
python app.py

pause
