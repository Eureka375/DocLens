# Remember AI Settings Implementation Plan

**Goal:** 同一电脑的当前 Windows 用户可跨重启复用 AI 设置和密钥。

**Architecture:** settings.py 封装 DPAPI 与原子密文存储；AnalysisController 只向 QML 暴露设置和密钥存在状态，按草稿地址解析密钥；现有预览授权保留。

**Tech Stack:** Python ctypes、Windows DPAPI、现有 Qt；不新增依赖。

**Spec:** [设计](../../design/2026-11-22-remember-ai-settings.md)

- [x] 编写并运行失败测试：DPAPI往返、密文无明文、损坏拒绝、原子保存失败保留旧文件、清除。
- [x] 实现 settings.py，运行存储测试。
- [x] 隔离界面测试设置目录；添加跨实例恢复、空输入复用、换地址阻止旧密钥、替换和清除及失败提示测试。
- [x] 实现控制器和QML保存/恢复/清除，运行完整测试并记录结果。

验证记录：完整123项通过，独立审查发现的临时文件清理异常已通过失败→修复测试验证。代码和交付记录按功能提交，推送结果见本轮最终回复。
