@echo off
:: start_service.bat
:: 启动 QuestionDemoService Windows 服务
:: 必须以管理员身份运行

chcp 65001 > nul
setlocal

:: ── 管理员权限自检 ────────────────────────────────────────
net session > nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 请以管理员身份运行本脚本。
    echo 右键脚本 -^> 以管理员身份运行
    exit /b 1
)

echo 正在启动 QuestionDemoService…
net start QuestionDemoService
if %errorlevel% neq 0 (
    echo [错误] 服务启动失败，请检查服务是否已安装：
    echo   scripts\install_service.bat
    exit /b 1
)
echo [OK] QuestionDemoService 已启动。

endlocal
