@echo off
cd /d "%~dp0"
echo Instalando o Jarvis...
py -3.12 -m venv .venv || python -m venv .venv
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
echo.
echo Pronto! Use iniciar.bat para abrir o Jarvis.
pause
