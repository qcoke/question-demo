# 答题站请求拦截器

底层、静默、自动化的本地 HTTP 流量拦截工具，基于 WinDivert / PyDivert。

当前阶段只完成 **Python 主程序**：
- 监听本机出站 TCP 流量
- 把答题接口的 `selected_option=A|B|C|D` 改写为 `selected_option=E`
- 用日志输出每次改写的来源、目的、payload 长度

打包 EXE、注册 NSSM 服务等环节后续再做。

## 1. 环境要求
- Windows 10 / 11
- Python 3.10+
- 管理员权限（加载 WinDivert 驱动需要）

## 2. 安装依赖

```powershell
pip install -r interceptor\requirements.txt
```

## 3. 启动 Django 服务（带日志）

```powershell
python manage.py runserver
```

后端 `submit_answer` 已加日志，控制台会打印每次收到的答案，例如：

```
2026-04-26 10:00:00,000 [INFO] quiz.views: submit_answer received attempt_id=1 order='1' selected_option='E' from 127.0.0.1
2026-04-26 10:00:00,010 [WARNING] quiz.views: submit_answer attempt_id=1 order=1 rejected invalid_option='E'
```

## 4. 启动拦截器

请使用 **以管理员身份运行** 的 PowerShell：

```powershell
python -m interceptor.main --port 8000 --verbose
```

可选参数：
- `--port`：Django 服务端口，默认 `8000`
- `--filter`：自定义 WinDivert 过滤表达式，覆盖 `--port`
- `--process-name`：只拦截指定进程名（不区分大小写），可重复，例：
  ```powershell
  python -m interceptor.main --process-name chrome.exe --process-name msedge.exe
  ```
- `--pid`：只拦截指定 PID，可重复
- `--record`：把每次改写事件写入 JSON
- `--log-dir`：录制存放目录，默认 `interceptor/logs`
- `--verbose`：输出 DEBUG 日志（含原始 payload 和改写后 payload）

启动成功会看到：

```
2026-04-26 10:00:00,000 [INFO] interceptor: Loading WinDivert with filter: outbound and tcp.DstPort == 8000
2026-04-26 10:00:00,001 [INFO] interceptor: Interceptor started. Press Ctrl+C to stop.
```

## 5. 验证效果
1. 浏览器打开 `http://127.0.0.1:8000/`
2. 答题并点击“下一题”
3. 拦截器控制台会打印：
   ```
   [INFO] interceptor: Rewriting selected_option -> E | 127.0.0.1:xxxx -> 127.0.0.1:8000 (len=...)
   ```
4. Django 控制台会打印：
   ```
   [WARNING] quiz.views: submit_answer attempt_id=N order=M rejected invalid_option='E'
   ```
5. 浏览器看到“请选择有效答案后再提交”的错误提示

## 6. 跑单元测试

```powershell
python -m unittest interceptor.tests
```

## 7. 录制 & 重放

开启录制：

```powershell
python -m interceptor.main --record --verbose
```

每次命中改写后会在 `interceptor/logs/` 下生成 JSON：

```
interceptor/logs/20260426-101530-123-0001.json
```

JSON 内容包含原始 / 改写后 payload（base64 + 文本视图），以及五元组、进程信息等。

把记录里的 **原始** ��求重放到本机 Django：

```powershell
python -m interceptor.replay interceptor\logs\20260426-101530-123-0001.json --url http://127.0.0.1:8000
```

把 **改写后** 请求重放（看后端会怎么处理 `selected_option=E`）：

```powershell
python -m interceptor.replay interceptor\logs\20260426-101530-123-0001.json --url http://127.0.0.1:8000 --rewritten
```

输出示例：

```
[INFO] interceptor.replay: Replaying POST http://127.0.0.1:8000/attempt/1/answer/ (body=... bytes)
[INFO] interceptor.replay: Response: 400 Bad Request
```

## 8. 设计要点

- 同长度替换（A/B/C/D → E）：不改变 TCP segment 长度，无需改 seq 或 Content-Length
- WinDivert v2 默认捕获 loopback，本机访问也能命中
- 任意异常都尽量将原包发出，避免“锁住”网络
- 注册 SIGINT 优雅退出，释放驱动 handle
- 进程过滤通过 psutil 周期性快照 (laddr.ip, laddr.port) → (pid, name) 实现，缓存 1 秒
- 录制使用同长度替换无需重组，单文件可独立重放

## 9. 已知限制
- 仅匹配明文 HTTP；HTTPS 请改用本地代理或先关闭 TLS
- 假设 form-urlencoded 字段不会跨多个 TCP 段；若启用 HTTP/2 或大 body 请额外做重组
- 仅在管理员权限下能加载驱动
- 进程过滤需要管理员权限，psutil 才能列出全部连接
- 录制目录如不可写，会记录警告但不影响主流程

