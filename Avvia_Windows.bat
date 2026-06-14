@echo off
REM Avvia Contabilità Automatica su Windows
REM Prima esecuzione: installa le dipendenze con:  pip install -r requirements.txt

cd /d "%~dp0"
python app.py
pause
