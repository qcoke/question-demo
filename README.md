# question-demo
答题站，简单的模型，用于测试 AI

这是一个基础 Django 答题应用，包含一个单选题题库系统，题目为 20 以内加减法。

## 功能说明

- 题库系统基于数据库模型 `Question`
- 所有题目均为单选题（A/B/C/D）
- 题目范围为 20 以内加减法
- 每次模拟测试随机抽取 10 道题
- 答题模式为逐题作答（不可跳题）
- 每次测试会生成独立记录，并保存每题作答与耗时
- 可在 Django Admin 查看题目、测试记录、每题作答明细

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

4. 创建管理员账号（用于查看后台数据）

```bash
python3 manage.py createsuperuser
```

5. 启动服务

```bash
python3 manage.py runserver
```

6. 打开浏览器访问

```text
http://127.0.0.1:8000/
```

7. 访问管理后台查看数据流向

```text
http://127.0.0.1:8000/admin/
```

后台关键数据：
- Quiz attempts：每次测试一条记录，包含分数、正确数、总耗时
- Attempt answers：每题作答详情，包含作答选项、正误、本题耗时

## 常用命令

- 重建题库（先清空再生成）：

```bash
python3 manage.py init_questions --reset
```

- 运行测试：

```bash
python3 manage.py test
```
