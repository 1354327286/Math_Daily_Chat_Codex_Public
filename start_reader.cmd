@echo off
setlocal
pushd "%~dp0"

set "READER_PYTHON=%CD%\.venv\Scripts\python.exe"
if not exist "%READER_PYTHON%" (
  echo The project Python environment was not found:
  echo   %READER_PYTHON%
  echo.
  echo Create the .venv environment first, then run this launcher again.
  pause
  popd
  exit /b 1
)

title Research Reader
echo Starting the local research reader...
echo Close this window or press Ctrl+C to stop it.
echo.

"%READER_PYTHON%" "%CD%\scripts\research_dashboard.py" --port 0 --open
set "READER_EXIT=%ERRORLEVEL%"

if not "%READER_EXIT%"=="0" (
  echo.
  echo The research reader stopped with an error.
  pause
)

popd
exit /b %READER_EXIT%
