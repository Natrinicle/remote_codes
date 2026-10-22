@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1 && (set "PY=py -3") || (set "PY=python")
%PY% -m pip install -q -r requirements.txt
%PY% labelbridge.py serve %*
