# Academic Smart Comparison Implementation Plan

**Goal:** 在现有 DocLens 中补齐学术标题、词级定位和可配置且严格校验的 AI 分析。

**Architecture:** 沿用 Snapshot → compare → prepare_analysis → AnalysisController → QML。ProviderConfig 只负责无密钥请求参数，网络、授权和缓存继续使用现有控制器。

**Tech Stack:** Python 3.13、PySide6、python-docx、pypdf、pytest；不新增依赖。

**Spec:** [增量设计](../../design/2026-11-22-academic-smart-comparison.md)

## Constraints and review focus

仅修改 DocLens；不纳入未跟踪发布目录。保留旧调用签名和字符高亮。检查数字正文误判、表格标题、单侧引用、缓存隔离以及请求失败后本地定位。

## Tasks

- [x] 先添加 tests/test_structure.py 的学术标题及 tests/test_core.py 的词级范围测试，运行观察失败；实现 structure.heading、Change 追加范围和 diff 的分词定位，运行相关测试。
- [x] 先添加 tests/test_analysis.py 的 provider 格式、学术分类、双侧引用、增删引用和章节证据测试，运行观察失败；新增 providers.py 并接入 analysis.py，运行相关测试。
- [x] 添加 tests/test_desktop.py 的配置传递和无效引用降级测试，运行观察失败；接入 analysis_ui.py 和 AnalysisDialog.qml；运行完整测试。
- [x] 增加 examples/学术比较/ 文本案例与说明，更新 README；在 docs/validation/academic-smart-comparison/ 记录实际文件、测试结果和未完成项。

## Execution evidence

首轮核心新增测试8项失败，实施后核心通过；界面测试先因缺少配置控件失败，接入后通过。发送预览章节漏显以新增断言复现后修复。独立审查发现数字正文误判，追加6项失败回归后收紧到学术标题词表。最终完整套件110 passed，见验证报告和日志。提交按结构比较、AI配置校验、交付记录拆分；推送结果在本轮最终回复中报告。
