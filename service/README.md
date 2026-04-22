# Windows 服务部署指南

> **适用平台**：仅 Windows（Windows 10 / 11 / Server 2016+）  
> **Python 版本**：Python 3.8+  
> **额外依赖**：`pywin32`  
> **运行权限**：必须以 **管理员身份** 运行所有脚本

---

## 为什么选择 pywin32 + Windows SCM？

`pywin32` 的 `win32serviceutil.ServiceFramework` 可直接将 Python 程序注册到
Windows **服务控制管理器（SCM）**，由 `services.exe` / `svchost.exe` 体系托管：

- 系统开机自动启动，无需用户登录
- 可在"服务"管理界面（`services.msc`）可视化管理
- 支持 `net start` / `net stop` / `sc` 等标准 Windows 命令
- 异常退出可配置自动重启策略
- 事件日志集成 Windows 事件查看器

---

## 快速上手

### 安装服务

```bat
scripts\install_service.bat
```

脚本会自动完成：
1. 安装 `pywin32`（`service/requirements-service.txt`）
2. 注册服务到 Windows SCM
3. 将服务启动类型设为"自动"
4. 立即启动服务

### 卸载服务

```bat
scripts\uninstall_service.bat
```

### 启动 / 停止 / 重启服务

```bat
scripts\start_service.bat
scripts\stop_service.bat
scripts\restart_service.bat
```

### 查看服务状态

```bat
scripts\status_service.bat
```

或在命令行中执行：

```bat
sc query QuestionDemoService
```

---

## 手动命令（在 `service\` 目录下执行）

```bat
python question_service.py install    :: 安装
python question_service.py remove     :: 卸载
python question_service.py start      :: 启动
python question_service.py stop       :: 停止
python question_service.py restart    :: 重启
python question_service.py debug      :: 前台调试（直接在控制台运行，Ctrl+C 退出）
```

---

## 修改监听端口 / 工作目录 / 入口命令

### 方法一：环境变量

在启动服务前设置：

```bat
set SERVICE_HOST=0.0.0.0
set SERVICE_PORT=8080
```

### 方法二：`service/service.env` 文件

在 `service/` 目录下创建 `service.env`（每行 `key=value`，`#` 开头为注释）：

```env
# 监听地址（默认 127.0.0.1）
SERVICE_HOST=0.0.0.0

# 监听端口（默认 8000）
SERVICE_PORT=8080
```

### 方法三：修改入口命令

若需更换启动方式（例如使用 `waitress`），编辑 `service/question_service.py` 中的
`build_entry_cmd()` 函数，将 `entry_cmd` 替换为目标命令列表，例如：

```python
entry_cmd = [python, "-m", "waitress", "--listen=0.0.0.0:8000", "config.wsgi:application"]
```

---

## 日志

| 位置 | 说明 |
|------|------|
| `logs/service.log` | 服务 stdout / stderr 及服务管理日志（滚动，最大 10 MB × 5 份） |
| Windows 事件查看器 | 路径：`事件查看器 → Windows 日志 → 应用程序`，来源：`QuestionDemoService` |

查看事件日志：

```bat
eventvwr.msc
```

或 PowerShell：

```powershell
Get-EventLog -LogName Application -Source QuestionDemoService -Newest 20
```

---

## 常见问题

### 1. 端口已被占用

检查哪个进程占用了端口：

```bat
netstat -ano | findstr :8000
```

然后根据 PID 终止进程，或修改 `service.env` 改用其他端口。

### 2. 权限不足

所有脚本（`scripts\*.bat`）必须以 **管理员身份** 运行。右键脚本 →「以管理员身份运行」。

### 3. `pywin32` 安装后服务注册失败

安装 `pywin32` 后需额外执行初始化脚本（只需一次）：

```bat
python -m pywin32_postinstall -install
```

### 4. 服务已安装但无法启动

查看 `logs/service.log` 与 Windows 事件查看器中的错误信息。常见原因：

- `DJANGO_SETTINGS_MODULE` 未设置（服务脚本已自动设置，通常不会出现此问题）
- 数据库未迁移：先在项目根目录执行 `python manage.py migrate`
- `SECRET_KEY` 或其他 Django 配置错误

### 5. 调试模式

以调试模式运行可在控制台直接查看输出：

```bat
cd service
python question_service.py debug
```

### 6. 更新代码后重启服务

```bat
scripts\restart_service.bat
```

---

## 依赖安装明细

```bat
pip install -r service/requirements-service.txt
python -m pywin32_postinstall -install
```
