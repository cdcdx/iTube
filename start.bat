@echo off
cd /d "%~dp0"

@REM echo *%VIRTUAL_ENV%*
if '%VIRTUAL_ENV%' neq '' (
    call .venv/Scripts/deactivate.bat
)

set PYTHON_HOME=%LOCALAPPDATA%\Programs\Python\Python311
echo %PATH% | findstr /C:%PYTHON_HOME% >nul
if %ERRORLEVEL% == 1 (
    echo %PYTHON_HOME%
    set PATH=%PYTHON_HOME%;%PYTHON_HOME%\Scripts;C:\WINDOWS\system32;C:\WINDOWS
)

@REM 读取配置到环境
set PYTHON_EXE=python.exe
set UVICORN_PORT=8000
setlocal enabledelayedexpansion
for /f "delims=" %%i in ('type ".env" ^|find /i "UVICORN_PORT="') do ( set %%i )

if "%1%"=="init" (
    if exist .venv (
        echo Virtual Environment already exists
        call .venv/Scripts/activate.bat
        pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    ) else (
        echo Install Virtual Environment ...
        python -m venv .venv
        call .venv/Scripts/activate.bat
        pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    )
    @REM pause>nul
) else if "%1%"=="clear" (
    rmdir /s/q "__pycache__"
) else if "%1%"=="kill" (
    @REM 检测端口是否占用
    echo Port:%UVICORN_PORT% Occupation Detection ...
    if %UVICORN_PORT% GTR 100 (
        for /f "tokens=5" %%i in ('netstat -ano ^|findstr ":%UVICORN_PORT%" ^|findstr "LISTENING"') do (
            echo Find the Port %UVICORN_PORT% PID: %%i
            taskkill /F /PID %%i
        )
    )
    if errorlevel 1 (
        echo No process found port %UVICORN_PORT%
    )

    @REM 检测所有进程是否运行
    echo Process:%PYTHON_EXE% Detection...
    for /f "tokens=1,2" %%i in ('tasklist ^| findstr "%PYTHON_EXE%"') do (
        echo Find the process %PYTHON_EXE% PID: %%j
        taskkill /F /PID %%j
    )
    if errorlevel 1 (
        echo No process found keyword %PYTHON_EXE%
    )
) else (
    @REM 检测端口是否占用
    echo Port:%UVICORN_PORT% Occupation Detection ...
    if %UVICORN_PORT% GTR 100 (
        for /f "tokens=1-5" %%i in ('netstat -ano ^|findstr ":%UVICORN_PORT%" ^|findstr "LISTENING"') do (
            echo The port %%i:%UVICORN_PORT% already used!
            exit /b
        )
    )

    echo Virtual Environment Activation ...
    call .venv/Scripts/activate.bat

    echo Launch backend/main.py ...
    python backend/main.py %1 %2 %3 %4 %5 %6
)
