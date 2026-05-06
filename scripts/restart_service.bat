@echo off
:: restart_service.bat
:: 重启 QuestionDemoService Windows 服务
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

echo ============================================================
echo  QuestionDemoService 重启
echo ============================================================

:: ── 停止（失败不影响后续启动）────────────────────────────
echo [步骤 1/2] 停止服务…
net stop QuestionDemoService
if %errorlevel% neq 0 (
    echo [提示] 停止失败（服务可能已处于停止状态），继续尝试启动…
) else (
    echo [OK] 服务已停止。
)

:: ── 稍等片刻，确保进程完全退出 ──────────────────────────
timeout /t 2 /nobreak > nul

:: ── 启动 ──────────────────────────────────────────────────
echo.
echo [步骤 2/2] 启动服务…
net start QuestionDemoService
if %errorlevel% neq 0 (
    echo [错误] 服务启动失败，请查看日志：logs\service.log
    exit /b 1
)
echo [OK] 服务已启动。

echo.
echo ============================================================
echo  [完成] QuestionDemoService 已成功重启。
echo ============================================================

endlocal
