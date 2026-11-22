# Review Workflow Implementation Plan

**Goal:** 在现有DocLens中完成可导出审阅与可核对覆盖的分批AI分析。

**Architecture:** 新增review.py管理核对状态/筛选与报告；CompareController接入清单、词级高亮和导出；analysis.py生成有界批次，AnalysisController顺序执行并保留逐组状态；QML保留原双栏并增加审阅面板。

**Tech Stack:** 现有Python/Qt与标准库，无新增依赖。

**Spec:** [设计](../../design/2026-11-22-review-workflow.md)

## Constraints / Review focus

不修改输入文档；HTML必须转义；备注不进入AI请求；过滤索引必须仍指向原比较编号；仅在预览授权后发送批次；取消/失败不自动重试、不发送剩余队列；旧结果只能与同一快照共存；关闭窗口必须正确取消队列。

- [x] Task 1：tests/test_review.py先验证筛选、备注、转义导出与保护原件失败；实现review.py；接入app.py和ReviewPane.qml并增加真实窗口操作测试。
- [x] Task 2：tests/test_analysis.py先验证4组分批、预算拆分、总预算拒绝；实现prepare_batches；tests/test_desktop.py验证覆盖遗漏、失败保留、取消阻止后续、显式补充授权；实现控制器顺序执行和界面覆盖列表。
- [x] Task 3：验证字符/词级切换不丢原文定位；补充能力边界说明、演示指南和验证报告；全套测试、独立审查。

执行结果：134项通过；独立审查的重跑结果丢失与直接勾选丢失两项均先复现再修复，见验证报告。功能与发布记录分别提交；打包、推送结果在本轮最终回复报告。
