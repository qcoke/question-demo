# question-demo
答题站，简单的模型，用于测试 AI

这是一个基础 Django 答题应用，包含一个单选题题库系统，题目为 20 以内加减法。

## 功能说明

- 题库系统基于数据库模型 `Question`
- 所有题目均为单选题（A/B/C/D）
- 题目范围为 20 以内加减法
- 每次模拟测试随机抽取 10 道题
- 前端为最简单的 Django Template 表单提交

## 快速启动

1. 安装依赖

```bash
pip install -r requirements.txt
```

2. 执行迁移

```bash
python3 manage.py migrate
```

3. 初始化题库

```bash
python3 manage.py init_questions
```

4. 启动服务

```bash
python3 manage.py runserver
```

5. 打开浏览器访问

```text
http://127.0.0.1:8000/
```

## 常用命令

- 重建题库（先清空再生成）：

```bash
python3 manage.py init_questions --reset
```

- 运行测试：

```bash
python3 manage.py test
```
