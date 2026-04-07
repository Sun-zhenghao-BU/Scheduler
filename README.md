# Scheduler Automation Workflow

## 中文说明

### 项目目标

这个仓库用于搭建一个本地自动化交付系统，让每一次改动都围绕一个 `OpenSpec change` 运转，并经过规格、实现、自审、修复、归档和同步远端的完整闭环。

### 当前能力

- 创建本地任务时自动创建并绑定一个 OpenSpec change
- `new-task` 会基于 OpenSpec 模板自动生成 `proposal.md`、`design.md`、`specs/.../spec.md`、`tasks.md`
- 生成结果会先在终端预览，确认后才写入 change 目录
- 在 `tasks/<task-id>/` 下生成本地执行工作区
- 按 `intake -> spec -> implement -> review -> fix -> release` 跟踪阶段
- 对阶段推进做严格门禁检查
- 记录本地验证结果
- 解析自我 review 结果，并用严重级别控制 release
- 在 `complete` 时归档 change，并自动执行 `git add`、`git commit`、`git push`

### 工作流闭环

推荐使用路径如下：

1. 执行 `new-task` 创建任务、OpenSpec change，并自动生成 OpenSpec 初稿
2. 在终端预览生成结果，输入 `y` 确认写入
3. `advance --stage spec`
4. `advance --stage implement`
5. 实现代码并记录说明
6. `verify` 运行本地验证
7. `advance --stage review`
8. 在 `review.md` 中记录自我 code review 结果
9. `review` 刷新 review 状态
10. 如果有问题则 `advance --stage fix`，修复后重新 `verify`
11. 回到 `review`，直到没有未解决的高优先级问题
12. `advance --stage release`
13. 在 `release.md` 中补齐发布说明
14. `complete` 归档 change 并自动 commit / push

### 阶段规则

- `spec -> implement`
  - 必须已有 `proposal.md`、`design.md`、`tasks.md`
  - `tasks.md` 中必须存在任务清单
  - 本地 `spec.md` 的摘要必须已填写
- `implement -> review`
  - 必须已有实现说明
  - 必须至少跑过一次验证
- `review -> release`
  - OpenSpec 任务必须全部完成
  - 不允许存在未解决的 `high` 级别问题
  - 最近一次验证必须通过
- `release -> complete`
  - `release.md` 必须填写
  - 归档、提交、推送任一步失败都会中止流程

### 常用命令

```powershell
python -m scheduler_automation.cli new-task --title "Build local workflow engine" --request "Create an OpenSpec-driven delivery loop"
python -m scheduler_automation.cli status
python -m scheduler_automation.cli show --task <task-id>
python -m scheduler_automation.cli advance --task <task-id> --stage spec
python -m scheduler_automation.cli verify --task <task-id>
python -m scheduler_automation.cli review --task <task-id>
python -m scheduler_automation.cli complete --task <task-id>
```

### 可视化看板

启动本地看板：

```powershell
$env:PYTHONPATH='src'
python -m scheduler_automation.dashboard --host 127.0.0.1 --port 8000
```

然后在浏览器打开：

`http://127.0.0.1:8000`

看板功能：

- 左侧查看所有任务的阶段和阻塞状态
- 右侧查看单任务详情
- 每 5 秒自动刷新一次
- 不直接修改数据，只用于观察进度和卡点

### 目录结构

```text
.codex/                   仓库内置 Codex 技能
docs/                     架构说明、设计文档、实现计划
openspec/                 OpenSpec 配置与 changes
tasks/                    本地任务工作区
src/scheduler_automation/ CLI 与工作流引擎实现
tests/                    标准库 unittest 测试
```

### 本地验证

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests -v
```

### 远端验证

- GitHub Actions 会在 push 和 pull request 时运行同样的测试命令。

## English

### Goal

This repository builds a local delivery automation system where every code change is driven by one `OpenSpec change` and must pass through a full loop of specification, implementation, self-review, bug fixing, archival, and remote sync.

### Current Capabilities

- automatic OpenSpec change creation and binding during task creation
- automatic OpenSpec-template-based generation of `proposal.md`, `design.md`, `specs/.../spec.md`, and `tasks.md` during `new-task`
- terminal preview plus explicit confirmation before generated artifacts are written
- a local execution workspace under `tasks/<task-id>/`
- gated stage tracking across `intake -> spec -> implement -> review -> fix -> release`
- strict transition checks before stage advancement
- local verification recording
- self-review parsing with severity-based release control
- archive plus automatic `git add`, `git commit`, and `git push` during `complete`

### Workflow Loop

Recommended flow:

1. Run `new-task` to create the local task, the bound OpenSpec change, and the generated artifact drafts.
2. Review the terminal preview and confirm the write.
3. Run `advance --stage spec`.
4. Run `autopilot --task <task-id>` to let the system advance through `implement`, `verify`, `review`, `fix`, and `release` automatically.
5. If autopilot stops in `fix`, apply the code changes it requires and run `autopilot` again.
6. When autopilot stops in `release`, run `complete` to archive the change and automatically commit and push.

### Stage Rules

- `spec -> implement`
  - `proposal.md`, `design.md`, and `tasks.md` must exist
  - `tasks.md` must contain checklist items
  - the local `spec.md` summary must be populated
- `implement -> review`
  - implementation notes must exist
  - at least one verification run must be recorded
- `review -> release`
  - all OpenSpec tasks must be complete
  - no open `high` severity findings may remain
  - the latest verification must pass
- `release -> complete`
  - `release.md` must be populated
  - any archive, commit, or push failure stops completion

### Common Commands

```powershell
python -m scheduler_automation.cli new-task --title "Build local workflow engine" --request "Create an OpenSpec-driven delivery loop"
python -m scheduler_automation.cli status
python -m scheduler_automation.cli show --task <task-id>
python -m scheduler_automation.cli autopilot --task <task-id>
python -m scheduler_automation.cli complete --task <task-id>
```

### Visual Dashboard

Start the local dashboard:

```powershell
$env:PYTHONPATH='src'
python -m scheduler_automation.dashboard --host 127.0.0.1 --port 8000
```

Then open:

`http://127.0.0.1:8000`

Dashboard behavior:

- left panel shows all tasks with stage and blocked state
- right panel shows task detail
- refreshes every 5 seconds
- read-only in the first version

### Repository Layout

```text
.codex/                   Codex skills bundled with this repository
docs/                     Architecture notes, design docs, and plans
openspec/                 OpenSpec configuration and change records
tasks/                    Local task workspaces
src/scheduler_automation/ CLI and workflow engine implementation
tests/                    Standard-library unittest suite
```

### Local Verification

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests -v
```

### Remote Verification

- GitHub Actions runs the same test command on pushes and pull requests.
