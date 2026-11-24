# Multi-document MVP Implementation Plan

**Goal:** 可运行的离线多文档证据研究闭环。

**Architecture:** 保持旧比对控制器，新增 research.py 核心、research_ui.py 后台控制器和 ResearchDialog.qml。复用 Snapshot 解析与结构定位，保存有版本的 JSON 快照，ZIP 不提取到文件系统。

**Tech Stack:** Python 3.13, PySide6, python-docx, pypdf, pytest, PyInstaller。

需求及验收依据：[正式需求](../../design/multi-document-mvp.md)。用户已要求直接完成需求文档和 MVP，按已明确范围实施，不增加设计审批环节。

- [ ] 任务1：先新增失败核心测试，增加 Markdown 支持、项目存储、共同项、证据、笔记和安全共享；运行核心测试。
- [ ] 任务2：新增桌面闭环测试，后台控制器和 QML 入口、矩阵/证据/目录/笔记/导出；运行新旧桌面测试。
- [ ] 任务3：生成四格式样例和指南，全量回归、独立审查、修复重要问题；构建 Windows 便携版并启动验证；提供验证报告、发布说明和校验值。
- [ ] 按功能提交并推送独立分支；不发布 GitHub Release，不合并 main。

审查关注：误报实际使用、快照证据一致性、无原文共享泄漏提示、恶意包资源上限、UI 后台状态和 UTF-16 跳转。
