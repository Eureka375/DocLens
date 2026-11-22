# DocLens v0.5.2 — 合并版 Windows 构建

此版本从 [PR #1](https://github.com/Eureka375/DocLens/pull/1) 和 [PR #2](https://github.com/Eureka375/DocLens/pull/2) 已合并的 `main` 源代码重新构建，不复用此前发布的 v0.5.1 二进制。

## 主要能力

- 结构化 TXT/DOCX/PDF 对比：段落、章节、表格文字与定位；支持词级或字符级高亮。
- PDF 页面原貌预览；DOCX 原貌依赖用户电脑安装 Microsoft Word，否则仍可使用文字比较。
- 保守识别移动、移动且修改的段落；跨章节相似内容不会直接误报为移动。
- 审阅清单、标记已核对、备注、HTML 比较报告与多组 AI 分批分析。
- AI 结果提供定位到左右原文的证据；新增逐字摘录验证与明确的语义人工复核提示。
- Windows 当前用户加密保存可选 AI 服务配置；离线比较和检索不需要 AI。

## 下载方式

在本仓库的 [GitHub Actions](https://github.com/Eureka375/DocLens/actions/workflows/windows-build.yml) 中，选择对应 `main` 最新提交且状态为成功的 **Windows build v0.5.2** 运行，打开运行详情底部的 **Artifacts**，下载 `DocLens-v0.5.2-Windows-x64`。

Artifact 包含：
- `DocLens-Setup-0.5.2-x64.exe`：当前用户安装版。
- `DocLens-V0.5.2-Windows.zip`：解压即用便携版。
- `DocLens-V0.5.2-Windows.zip.sha256`、`SHA256SUMS.txt`：校验值。
- `BUILD_INFO.txt` 和 `package-results.json`：源码 SHA 与测试记录。

**注意：** 安装包未签名，可能出现 Windows SmartScreen 未知发布者提示。只从仓库对应运行下载，不要使用第三方镜像；核验压缩包和安装程序 SHA256。便携版必须解压并保留整个 `DocLens` 目录，不能只复制 EXE。此版本并不自动替换 v0.5.1 的 GitHub Release 下载链接。

## 验证策略

构建工作流先运行 Windows 完整 pytest，随后创建 PyInstaller onedir，校验冻结程序中的必要模块、三类文档预览与 GUI 正常启动/关闭，之后用 Inno Setup 打包并执行静默安装与启动冒烟测试。最后计算两个包的 SHA256，保留 CI 产物。

该测试不覆盖用户电脑的全部 Windows 版本、杀毒软件、Microsoft Word 自动化环境或真实在线 AI API；需在用户机器上进行最终验收。
