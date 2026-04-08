## Why

背景：
当前 workflow 已经有任务状态、阶段、review、verify、release 信息，但缺少一键汇总导出能力，不方便归档和分享。

目标：
提供一个命令，将单个任务导出为两种报告：
1) Markdown 报告（便于阅读）
2) JSON 报告（便于系统集成）

范围：
- 新增命令：report --task <task-id> --format md|json|both
- 报告内容至少包含：
  - task_id, title, current_stage, change_name
  - blocked_reasons
  - verification status
  - review findings summary（high/medium/low）
  - OpenSpec tasks progress（complete/total）
  - latest timeline entries
- 输出目录：tasks/<task-id>/exports/
- 文件名包含时间戳

非目标：
- 不做远程上传
- 不做多任务批量导出
- 不改现有 complete 流程

验收标准：
1) 命令执行成功后，在 exports 目录能看到 md/json 文件
2) 缺失 task-id 时返回明确错误
3) 报告字段完整且和 show 页面关键信息一致
4) 单元测试覆盖成功路径和失败路径 needs a structured OpenSpec change so the work can move from request to implementation with clear artifacts and reviewable scope.

## What Changes

- Introduce the `task-115419` capability for this change.
- Capture the requested work as OpenSpec proposal, design, spec, and tasks artifacts.
- Provide an implementation path that can be reviewed and refined before coding.

## Capabilities

### New Capabilities
- `task-115419`: 功能名称：导出任务执行报告

### Modified Capabilities
- None.

## Impact

- Affected area: 背景：
当前 workflow 已经有任务状态、阶段、review、verify、release 信息，但缺少一键汇总导出能力，不方便归档和分享。

目标：
提供一个命令，将单个任务导出为两种报告：
1) Markdown 报告（便于阅读）
2) JSON 报告（便于系统集成）

范围：
- 新增命令：report --task <task-id> --format md|json|both
- 报告内容至少包含：
  - task_id, title, current_stage, change_name
  - blocked_reasons
  - verification status
  - review findings summary（high/medium/low）
  - OpenSpec tasks progress（complete/total）
  - latest timeline entries
- 输出目录：tasks/<task-id>/exports/
- 文件名包含时间戳

非目标：
- 不做远程上传
- 不做多任务批量导出
- 不改现有 complete 流程

验收标准：
1) 命令执行成功后，在 exports 目录能看到 md/json 文件
2) 缺失 task-id 时返回明确错误
3) 报告字段完整且和 show 页面关键信息一致
4) 单元测试覆盖成功路径和失败路径
- Artifact flow: proposal, design, specs, tasks
- Delivery flow: implementation, review, fix, and release tracking
