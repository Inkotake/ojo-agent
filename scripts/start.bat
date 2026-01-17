@echo off
chcp 65001 >nul
REM OJO v9.0 启动脚本 (Windows)

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..

cd /d %PROJECT_ROOT%

REM 加载环境变量
if exist .env (
    for /f "usebackq tokens=1,2 delims==" %%a in (.env) do (
        if not "%%a"=="" if not "%%a:~0,1%"=="#" set "%%a=%%b"
    )
)

REM 默认值
if not defined OJO_HOST set OJO_HOST=0.0.0.0
if not defined OJO_PORT set OJO_PORT=8000
if not defined OJO_DEBUG set OJO_DEBUG=false

echo ==========================================
echo   OJO v9.0 - OJ批处理助手
echo ==========================================
echo 服务器地址: http://%OJO_HOST%:%OJO_PORT%
echo API文档: http://%OJO_HOST%:%OJO_PORT%/docs
echo 调试模式: %OJO_DEBUG%
echo ==========================================

REM 检查虚拟环境
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo [信息] 已激活虚拟环境
)

REM 检查依赖
pip install -q -r requirements.txt

REM 启动服务
cd src
python api_server.py

pause
