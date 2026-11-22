# DocLens Windows 发布包

- V0.3.1 为待合并的增强版候选：支持移动并修改、AI 摘录校验、标注基准对照和 Windows 安装包。详见 [发布候选说明](v0.3.1/README.md)；下载候选文件请从 PR 对应的 GitHub Actions Artifacts 获取。
- V0.3.0 PDF 与移动识别版为当前主线版本，内含两份 PDF 测试样例。[发布说明](v0.3.0/README.md)
- V0.2.1 DeepSeek 兼容版支持 DeepSeek 官方接口。
- V0.2.0 课程首版包含真实文档比对、文件夹检索和 AI 分析。
- T01 Windows 原型用于复现当时的技术验证。

解压完整目录后双击里面的 `DocLens.exe`（T01 原型使用 `DocLensT01.exe`）。保留与可执行文件放在一起的运行依赖。V0.3.0 也可从项目的 `dist/v0.3.0/DocLens/` 直接启动。

新版本的验证完成后，将发布 ZIP 放入对应版本目录。`dist/` 保留可运行目录。大型发布包保存在本机归档，Git 管理源码、说明和验证记录。
