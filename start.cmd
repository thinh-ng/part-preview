@echo off
cd /d "%~dp0"
if not exist web\dist\index.html (
  pushd web
  call npm ci || exit /b 1
  call npm run build || exit /b 1
  popd
)
start "" http://127.0.0.1:8765/
python server.py
