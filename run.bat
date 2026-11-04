@echo off
setlocal
py -3 -X utf8 "%~dp0run.py" %*
exit /b %errorlevel%
