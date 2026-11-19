@echo off
rem Demarre l'assistant LinkedIn dans cette console.
rem Arret : Ctrl+C. Log complet : data\bot.log
cd /d "%~dp0"
if not exist data mkdir data
.venv\Scripts\linkedin-assistant.exe --config config.toml >> data\bot.log 2>&1
pause
