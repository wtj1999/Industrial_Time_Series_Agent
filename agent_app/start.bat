@echo off
REM Industrial Time Series Agent System - Startup Script

echo ========================================
echo 工业时间序列多智能体系统启动脚本
echo ========================================
echo.

REM Check if virtual environment exists
if exist "venv\Scripts\activate.bat" (
    echo 激活虚拟环境...
    call venv\Scripts\activate.bat
) else (
    echo 虚拟环境未找到，创建虚拟环境...
    python -m venv venv
    call venv\Scripts\activate.bat

    echo.
    echo 安装依赖...
    pip install -r requirements.txt
)

echo.
echo ========================================
echo 选择启动模式:
echo ========================================
echo.
echo 1. 命令行界面 (CLI)
echo 2. API 服务器 (REST API)
echo 3. 生成测试数据
echo 4. 运行系统测试
echo 5. 查看示例代码
echo.

set /p choice="请选择 (1-5): "

if "%choice%"=="1" (
    echo.
    echo 启动命令行界面...
    python main.py
) else if "%choice%"=="2" (
    echo.
    echo 启动 API 服务器...
    echo 服务器将在 http://0.0.0.0:5000 启动
    echo.
    python api.py
) else if "%choice%"=="3" (
    echo.
    echo 生成测试数据...
    python generate_test_data.py
    echo.
    pause
) else if "%choice%"=="4" (
    echo.
    echo 运行系统测试...
    python test_system.py
    echo.
    pause
) else if "%choice%"=="5" (
    echo.
    echo 显示示例代码...
    start example_usage.py
    echo 示例代码已在编辑器中打开
    echo.
    pause
) else (
    echo.
    echo 无效选择，退出...
    pause
)
