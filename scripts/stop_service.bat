@echo off
:: stop_service.bat
:: 停止 QuestionDemoService Windows 服务
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

echo 正在停止 QuestionDemoService…
net stop QuestionDemoService
if %errorlevel% neq 0 (
    echo [警告] 服务停止失败（可能已经处于停止状态）。
    exit /b 1
)
echo [OK] QuestionDemoService 已停止。

endlocal
