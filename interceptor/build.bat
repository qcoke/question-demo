@echo off
REM ============================================================
REM 一键打包 quiz_interceptor.exe
REM 用法: 在 Windows 上双击运行,或在 cmd 里执行 build.bat
REM
REM 目标系统兼容性: Windows 7 SP1 x64 / Windows 8.1 / Windows 10/11
REM 打包机必须使用 Python 3.9.x (64-bit),3.10+ 在 Win7 上启动失败。
REM 推荐 Python 3.9.13:
REM   https://www.python.org/downloads/release/python-3913/
REM ============================================================

setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [!] 未找到 python,请先安装 Python 3.9.x ^(64-bit^) 并勾选 Add to PATH
  pause
  exit /b 1
)

REM 校验 Python 版本必须是 3.9.x (产出的 exe 才能在 Win7 上运行)
python -c "import sys; sys.exit(0 if sys.version_info[:2]==(3,9) else 1)"
if errorlevel 1 (
  echo [!] 检测到的 Python 版本不是 3.9.x
  python --version
  echo [!] 为兼容 Windows 7,请改用 Python 3.9.13 ^(64-bit^) 重新打包
  pause
  exit /b 1
)

echo [*] 升级 pip 并安装依赖 (锁定 Win7 兼容版本)...
python -m pip install --upgrade "pip<24.1" || goto :err
python -m pip install -r requirements.txt || goto :err

echo [*] 开始打包 (PyInstaller --onefile)...
python -m PyInstaller ^
  --onefile ^
  --console ^
  --name quiz_interceptor ^
  --collect-binaries pydivert ^
  --collect-data pydivert ^
  interceptor.py || goto :err

echo.
echo [OK] 打包完成: %cd%\dist\quiz_interceptor.exe
echo.
echo 运行示例 (在管理员 cmd 里执行):
echo     dist\quiz_interceptor.exe --host 192.168.1.10 --port 8000
echo.
pause
exit /b 0

:err
echo.
echo [!] 构建失败,请查看上方报错。
pause
exit /b 1
