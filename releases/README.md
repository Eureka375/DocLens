# DocLens Windows 发布包

- V0.5.1 为当前版本，AI解释和状态直接显示在首页左侧分组。[下载ZIP](https://github.com/Eureka375/DocLens/releases/download/v0.5.1/DocLens-V0.5.1-Windows.zip) · [发布说明](v0.5.1/README.md)
- V0.5.0 包含审阅清单、核对备注、HTML导出、词级高亮和AI分批覆盖。[下载ZIP](https://github.com/Eureka375/DocLens/releases/download/v0.5.0/DocLens-V0.5.0-Windows.zip) · [发布说明](v0.5.0/README.md)
- V0.4.2 将AI等待上限放宽至120秒。[下载ZIP](https://github.com/Eureka375/DocLens/releases/download/v0.4.2/DocLens-V0.4.2-Windows.zip) · [发布说明](v0.4.2/README.md)
- V0.4.1 包含学术比较、AI请求格式配置和加密记住API Key。[下载ZIP](https://github.com/Eureka375/DocLens/releases/download/v0.4.1/DocLens-V0.4.1-Windows.zip) · [发布说明](v0.4.1/README.md)
- V0.4.0 原貌比较版，支持 Word/PDF 原始页面、缩放和页面差异标记。[下载ZIP](https://github.com/Eureka375/DocLens/releases/download/v0.4.0/DocLens-V0.4.0-Windows.zip) · [发布说明](v0.4.0/README.md)
- V0.3.1 结构化比较版，内含 TXT 结构化与 PDF 测试样例。[下载ZIP](https://github.com/Eureka375/DocLens/releases/download/v0.3.1/DocLens-V0.3.1-Windows.zip) · [发布说明](v0.3.1/README.md)
- V0.3.0 PDF 与移动识别版。[下载ZIP](https://github.com/Eureka375/DocLens/releases/download/v0.3.0/DocLens-V0.3.0-Windows.zip) · [发布说明](v0.3.0/README.md)
- V0.2.1 DeepSeek 兼容版支持 DeepSeek 官方接口。[历史包下载](https://github.com/Eureka375/DocLens/releases/download/archive-v0.2.1/DocLens-V0.2.1-DeepSeek-Windows.zip)
- V0.2.0 课程首版包含真实文档比对、文件夹检索和 AI 分析。[历史包下载](https://github.com/Eureka375/DocLens/releases/download/archive-v0.2.0/DocLens-V0.2-Windows.zip)
- T01 Windows 原型用于复现当时的技术验证。[原型下载](https://github.com/Eureka375/DocLens/releases/download/archive-t01/DocLens-T01-Windows.zip)

解压完整目录后双击里面的 `DocLens.exe`（T01 原型使用 `DocLensT01.exe`）。保留与可执行文件放在一起的运行依赖。V0.5.1 也可从项目的 `dist/v0.5.1/DocLens/` 直接启动。

新版本的验证完成后，将发布 ZIP 放入对应版本目录，作为GitHub Release附件提供下载；每版附SHA-256校验文件。`dist/` 保留可运行目录，ZIP仍不加入Git历史。[全部在线版本](https://github.com/Eureka375/DocLens/releases)。

前三个早期包使用 `archive-` 标签：尚未追溯到可与原包一一对应的源码快照，标签指向仓库初始化提交，仅作下载归档入口；不能用该提交重建原包。T01是一次性原型，不是正式产品。其余版本关联已记录的发布提交。T01的在线附件名使用ASCII，原ZIP内容和摘要保持不变。
