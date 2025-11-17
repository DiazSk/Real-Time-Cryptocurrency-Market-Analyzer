@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
set PYTHONPATH=%CD%\src
python src\consumers\simple_consumer.py
pause

