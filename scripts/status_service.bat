@echo off
:: status_service.bat
:: 查询 QuestionDemoService Windows 服务当前状态

chcp 65001 > nul
setlocal

echo ============================================================
echo  QuestionDemoService 状态查询
echo ============================================================
sc query QuestionDemoService
if %errorlevel% neq 0 (
    echo.
    echo [提示] 服务未安装，请先运行：scripts\install_service.bat
)

endlocal
