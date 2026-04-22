@echo off
:: install_service.bat
:: 安装并启动 QuestionDemoService Windows 服务
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

:: ── 路径定位（脚本位于 scripts\，仓库根为上一层）─────────
set "ROOT_DIR=%~dp0.."
pushd "%ROOT_DIR%"

echo ============================================================
echo  QuestionDemoService 安装程序
echo ============================================================

:: ── 检查 Python ───────────────────────────────────────────
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请安装 Python 3.8+ 并加入 PATH。
    popd
    exit /b 1
)
echo [OK] Python 已就绪：
python --version

:: ── 安装服务依赖 ──────────────────────────────────────────
echo.
echo [步骤 1/4] 安装服务依赖（service\requirements-service.txt）…
pip install -r service\requirements-service.txt
if %errorlevel% neq 0 (
    echo [错误] 依赖安装失败，请检查网络或 pip 配置。
    popd
    exit /b 1
)
echo [OK] 依赖安装完成。

:: ── 初始化 pywin32（幂等操作）────────────────────────────
echo.
echo [步骤 2/4] 初始化 pywin32 运行时…
python -m pywin32_postinstall -install > nul 2>&1
echo [OK] pywin32 初始化完成（若已初始化则忽略）。

:: ── 注册服务 ──────────────────────────────────────────────
echo.
echo [步骤 3/4] 注册 Windows 服务…
python service\question_service.py install
if %errorlevel% neq 0 (
    echo [错误] 服务注册失败，请查看上方错误信息。
    popd
    exit /b 1
)
echo [OK] 服务注册成功。

:: ── 设置自动启动并立即启动 ───────────────────────────────
echo.
echo [步骤 4/4] 设置启动类型为"自动"并启动服务…
sc config QuestionDemoService start= auto
net start QuestionDemoService
if %errorlevel% neq 0 (
    echo [警告] 服务启动失败，请使用以下命令排查：
    echo   sc query QuestionDemoService
    echo   type logs\service.log
    popd
    exit /b 1
)

echo.
echo ============================================================
echo  [完成] QuestionDemoService 已安装并正在运行。
echo  访问地址：http://127.0.0.1:8000/
echo  查看日志：logs\service.log
echo ============================================================

popd
endlocal
