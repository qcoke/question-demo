@echo off
:: uninstall_service.bat
:: 停止并卸载 QuestionDemoService Windows 服务
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

:: ── 路径定位 ──────────────────────────────────────────────
set "ROOT_DIR=%~dp0.."
pushd "%ROOT_DIR%"

echo ============================================================
echo  QuestionDemoService 卸载程序
echo ============================================================

:: ── 停止服务（若正在运行）────────────────────────────────
echo [步骤 1/2] 停止服务（若未运行则忽略）…
net stop QuestionDemoService > nul 2>&1
echo [OK] 停止操作完成。

:: ── 卸载服务 ──────────────────────────────────────────────
echo.
echo [步骤 2/2] 卸载 Windows 服务…
python service\question_service.py remove
if %errorlevel% neq 0 (
    echo [错误] 卸载失败，请查看上方错误信息。
    popd
    exit /b 1
)

echo.
echo ============================================================
echo  [完成] QuestionDemoService 已成功卸载。
echo ============================================================

popd
endlocal
