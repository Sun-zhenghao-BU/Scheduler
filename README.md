# Scheduler Automation

一个面向本地开发团队的调度器，用来把“需求确认 -> 任务推进 -> 项目工作区 -> 开发提案 -> 测试验证”串成一条可持续运行的最小闭环。

它不是通用项目管理系统，而是一个偏工程执行面的控制台：

- 用项目绑定本地代码目录
- 在项目内创建和推进任务
- 在进入开发前强制做需求确认
- 在绑定目录内浏览文件、生成修改提案、运行测试
- 为后续接入 OpenSpec / 多代理执行保留状态和接口

## 当前最小链路

当前版本已经支持下面这条最小工作流：

1. 启动 Web UI
2. `打开文件夹`
3. 从已挂载的磁盘根中选择一个项目目录
4. 自动创建项目或打开已绑定项目
5. 在项目内创建任务
6. 在任务详情页补充并确认需求
7. 进入开发阶段
8. 在项目工作区中浏览文件、生成修改提案、运行测试

## 核心概念

### Project

项目是一个带 `root_path` 的容器。`root_path` 指向一个本地代码目录。

### Task

任务是项目内的执行单元，持久化在：

```text
tasks/<task-id>/
```

每个任务自带：

- `request.md`
- `spec.md`
- `implementation.md`
- `review.md`
- `fixes.md`
- `release.md`
- `journal.md`
- `metadata.json`
- `requirements.json`

### Stage

任务阶段固定为：

1. `intake`
2. `spec`
3. `implement`
4. `review`
5. `fix`
6. `release`

其中 `implement` 前必须先完成需求确认。

## 目录结构

```text
.codex/                          本仓库内的 Codex / OpenSpec 技能
docs/                            架构与计划文档
openspec/                        OpenSpec 配置
tasks/                           任务工作区与持久化状态
src/scheduler_automation/        后端、工作流、项目与工作区逻辑
src/web/                         React 前端
tests/                           Python 测试
docker-compose.yml               Docker 部署入口
Dockerfile                       镜像构建定义
```

## 运行方式

支持两种运行方式：

1. Docker 部署
2. 本机开发模式

---

## 方式一：Docker 部署

这是推荐给其他使用者的运行方式。

### 1. 环境要求

- Docker Desktop
- Windows 主机
- 可访问 `C:`、`D:` 的本地代码目录

### 2. 启动前准备

设置下面几个环境变量：

```powershell
$env:PROJECT_ROOT="D:\Work\Scheduler"
$env:HOST_C_PATH="C:\"
$env:HOST_D_PATH="D:\"
```

含义：

- `PROJECT_ROOT`
  当前调度器仓库自身路径，会挂到容器里的 `/workspace/project`
- `HOST_C_PATH`
  宿主机 `C:` 盘挂载到容器里的 `/host/c`
- `HOST_D_PATH`
  宿主机 `D:` 盘挂载到容器里的 `/host/d`

### 3. 启动命令

```powershell
docker compose up -d --build
```

如果拉基础镜像很慢，可以先手动拉：

```powershell
docker pull node:24-alpine
docker pull python:3.13-slim
docker compose up -d --build
```

### 4. 启动结果

默认会启动一个容器：

- Web + API 地址：`http://localhost`
- 健康检查：`http://localhost/healthz`

容器内重要挂载：

- `/workspace/project`
  调度器当前仓库
- `/host/c`
  宿主机 `C:`
- `/host/d`
  宿主机 `D:`

### 5. Docker 下“打开文件夹”的工作方式

因为后端运行在容器里，所以它只能访问**已经挂载进容器的宿主路径**。

这意味着：

- UI 里“打开文件夹”不是任意访问主机上的所有路径
- 它能浏览的是：
  - `C:` 盘映射到 `/host/c`
  - `D:` 盘映射到 `/host/d`

前端目录选择器会从这两个盘根开始逐层展开。

### 6. 停止、重启、重建

停止：

```powershell
docker compose down
```

停止并删除卷：

```powershell
docker compose down -v
```

修改代码后重建：

```powershell
docker compose up -d --build
```

查看日志：

```powershell
docker compose logs -f
```

---

## 方式二：本机开发模式

适合做前后端调试，不适合作为统一交付方式。

### 1. Python 后端

安装依赖：

```powershell
pip install -e ".[server]"
```

启动后端：

```powershell
$env:PYTHONPATH="src"
uvicorn scheduler_automation.api.app:app --host 0.0.0.0 --port 8000
```

### 2. 前端

```powershell
cd src/web
npm install
npm run dev
```

浏览器访问：

```text
http://localhost:5173
```

> 本机开发模式下，如果你希望目录选择逻辑完全按 Windows 原始路径工作，建议后端也在宿主机而不是 Docker 中运行。

## 首次使用流程

### 1. 打开系统

Docker 模式：

```text
http://localhost
```

本机开发模式：

```text
http://localhost:5173
```

### 2. 打开本地项目

在首页点击：

```text
打开文件夹
```

然后：

1. 选择一个磁盘根
2. 逐层展开目录
3. 点击要绑定的项目目录
4. 确认创建或打开项目

### 3. 创建任务

进入项目后：

1. 点击 `新建任务`
2. 填写标题
3. 可选填写初始需求描述

### 4. 需求确认

进入任务详情页后：

1. 在“需求确认”区域补充需求
2. 填写最终需求摘要
3. 点击“确认需求”

确认后才允许进入 `implement`。

### 5. 项目工作区

在项目侧边栏打开：

```text
项目工作区
```

你可以：

- 浏览绑定目录内的文件
- 选择文件作为开发上下文
- 输入修改要求生成提案
- 在项目目录下运行测试命令

## LLM 配置

进入：

```text
系统设置
```

填写：

- API Key
- Base URL
- Model

然后点击测试连接。

支持任何 OpenAI 兼容接口，例如：

- OpenAI
- DeepSeek
- Qwen 兼容网关
- Ollama 的兼容接口

## API 概览

### Projects

- `GET /api/projects/`
- `POST /api/projects/`
- `PUT /api/projects/{project_id}`
- `GET /api/projects/{project_id}`
- `GET /api/projects/{project_id}/tasks`
- `GET /api/projects/open-roots`
- `GET /api/projects/open-roots/{root_id}/children`

### Tasks

- `GET /api/tasks/`
- `POST /api/tasks/`
- `GET /api/tasks/{task_id}`
- `POST /api/tasks/{task_id}/advance`
- `POST /api/tasks/{task_id}/log`
- `POST /api/tasks/{task_id}/requirements/messages`
- `POST /api/tasks/{task_id}/requirements/confirm`

### Workspace / Development

- `GET /api/workspace/`
- `GET /api/workspace/tree`
- `GET /api/workspace/file`
- `POST /api/development/propose`
- `POST /api/development/apply`
- `POST /api/development/test`

## 验证方式

### Python 测试

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests -v
```

### 前端构建

```powershell
cd src/web
npm run build
```

## 常见问题

### 1. 打开文件夹时看不到目录

先检查 Docker 是否真的挂载了 `C:` 和 `D:`：

```powershell
docker compose exec scheduler ls /host
```

预期至少能看到：

```text
c
d
```

### 2. 项目已存在但显示“未绑定目录”

在首页的“已有项目”里点击：

```text
绑定目录
```

重新选择项目目录即可。

### 3. 测试命令执行失败

先确认：

- 该项目目录里已经安装依赖
- 命令属于允许列表
- 后端容器能访问该目录

当前允许的测试入口主要是：

- `npm test`
- `pnpm test`
- `yarn test`
- `pytest`
- `python -m pytest`

### 4. 打开文件夹很慢

当前目录树是按层加载，不会全盘递归。

如果仍然很慢，通常是：

- 选中了体量很大的系统目录
- 磁盘本身响应慢
- Docker Desktop 文件共享性能有限

建议从明确的代码目录往下走，不要在系统目录里深度浏览。

## 后续建议

如果这个调度器要给更多人使用，下一步建议优先做：

1. README 的截图和操作录屏
2. 一键初始化脚本
3. Docker 健康检查和启动自检
4. 项目目录权限与白名单校验
5. 更明确的任务执行审计日志

## License

按你的项目策略处理。当前仓库未单独声明许可证时，请先在团队内部使用。
