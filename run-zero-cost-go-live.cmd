@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=.venv-zero-cost\Scripts\python.exe"
set "CONFIG=config\zero_cost_operator.json"

if exist "%PYTHON%" goto :config

where py >nul 2>nul
if not errorlevel 1 goto :bootstrap_py

where python >nul 2>nul
if not errorlevel 1 goto :bootstrap_python

echo Python 3 nao encontrado no PATH. Instale Python 3 e execute novamente.
exit /b 10

:bootstrap_py
py -3 scripts\bootstrap_zero_cost.py
if errorlevel 1 exit /b 11
goto :config

:bootstrap_python
python scripts\bootstrap_zero_cost.py
if errorlevel 1 exit /b 11

:config
if not exist "%CONFIG%" (
  copy /Y "config\zero_cost_operator.example.json" "%CONFIG%" >nul
  echo Configuracao criada em %CONFIG%.
  echo Preencha os caminhos reais, direitos de mercado e arquivos autorizados.
  echo Depois execute este arquivo novamente.
  exit /b 3
)

"%PYTHON%" scripts\go_live_zero_cost.py --config "%CONFIG%" --evidence-dir outputs\go-live
exit /b %errorlevel%
