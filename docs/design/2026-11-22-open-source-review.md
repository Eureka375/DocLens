# 开源核验与本轮实现决策

核验日期：2026-11-22。先检查了当前 README、原实施计划、解析/比较/检索/AI/窗口代码及测试。项目是独立 Python 3.13 / Qt 桌面应用；没有操作 FolioMind。现有功能包括 TXT/DOCX/文本 PDF、字符偏移证据、唯一块移动、SQLite FTS5 trigram 检索和可选 AI 解释。

引用聊天的缓存只有用户问题，未提供上轮回复中的仓库地址，当前工具也没有读取该聊天全文的入口。因此下面固定使用完整仓库名核验；尤其 DocGraph 有多个同名项目，不能声称就是上轮所指的那个。下载的是各仓库当时的 main 分支，未运行其模型或整个应用。GitHub API 限流、Git 连接失败后改用源码归档读取；关键文件的 SHA-256 见[核验清单](../validation/structured-comparison/upstream-sources.json)，后续复核应比较内容摘要，不将浮动 main 链接视为固定版本。

## 六个项目

### Doc Drift Analyzer：cfuglestad/doc-drift-analyzer

[源码 alignment.py](https://github.com/cfuglestad/doc-drift-analyzer/blob/main/src/alignment.py) 对旧章节逐个寻找未使用的新章节，标题分数占 0.4、正文占 0.6，是贪心一对一匹配；词法后端为 SequenceMatcher，可选本地语义/混合后端。[许可证](https://github.com/cfuglestad/doc-drift-analyzer/blob/main/LICENSE)为 MIT。

采用“章节先行，再细看文字”的设计思路。本轮不移植贪心全局配对，也不照搬上游小样本指标；中文合同是否适用需要自己的案例集。

### dupey：NomaDamas/dupey

[near.rs](https://github.com/NomaDamas/dupey/blob/main/crates/dupey-core/src/near.rs) 使用字符 5-gram、128 维 MinHash，再验证精确 shingle 重合与包含率；正文指纹是 SHA-256。[rank.rs](https://github.com/NomaDamas/dupey/blob/main/crates/dupey-core/src/rank.rs)优先内部修改时间，否则文件修改时间，只给最新候选。[许可证](https://github.com/NomaDamas/dupey/blob/main/LICENSE)为 MIT。

适合作为未来文档家族候选筛选的参考。词法近似、包含关系和“更新得较晚”均不足以证明版本继承，不应据此自动删除或覆盖。

### Docling：docling-project/docling

[PDF 管线](https://github.com/docling-project/docling/blob/main/docling/pipeline/standard_pdf_pipeline.py)有版面、OCR、表格与阅读顺序等独立处理阶段；结构化结果使用 docling-core 类型。[项目许可证](https://github.com/docling-project/docling/blob/main/LICENSE)为 MIT；可选模型权重及依赖仍须按实际选择另行核验。

采用统一结构块和来源位置的思路，保留适配空间。本轮未安装 Docling，未加入 OCR、版面模型或下载模型的启动路径；便携版成本与复杂 PDF 正确率尚未实测。

### DocDiff AI：mxthsu/docdiff-ai

[version_diff.py](https://github.com/mxthsu/docdiff-ai/blob/main/src/docdiff_ai/version_diff.py)按相同文本、唯一标题、词法相似依次匹配，保留行号与片段证据；词法路径有 Jaccard 预筛选及 SequenceMatcher。[许可证](https://github.com/mxthsu/docdiff-ai/blob/main/LICENSE)为 MIT。

采用可审计的确定性比较和原文证据，继续使用 DocLens 已有字符偏移及 AI 证据校验；不将词法相似当成语义一致。

### DocGraph：Detective-XH/DocGraph（本次选定对象）

[schema.go](https://github.com/Detective-XH/DocGraph/blob/main/internal/store/schema.go)定义 FTS5 trigram；[search_collectors.go](https://github.com/Detective-XH/DocGraph/blob/main/internal/store/search_collectors.go)有字段权重 BM25，短查询回退另有处理。[pairwise.go](https://github.com/Detective-XH/DocGraph/blob/main/internal/similarity/pairwise.go)的默认文档相似度组合 TF-IDF 余弦、共同引用及标签。[许可证](https://github.com/Detective-XH/DocGraph/blob/main/LICENSE)为 MIT。

DocLens 已有同类本地 trigram/短词回退基础；图关系和主题相似度不替代两文档差异。本轮暂不引入图谱或 MCP 服务。

### Paperless-ngx：paperless-ngx/paperless-ngx

本次源码的[检索后端](https://github.com/paperless-ngx/paperless-ngx/blob/main/src/documents/search/_backend.py)导入 Tantivy，通过 whoosh-compat 处理查询语法，不能仅凭旧资料称其为 Whoosh 后端。[consumer.py](https://github.com/paperless-ngx/paperless-ngx/blob/main/src/documents/consumer.py)结合[SHA-256 文件校验](https://github.com/paperless-ngx/paperless-ngx/blob/main/src/documents/utils.py)防重复导入。[许可证](https://github.com/paperless-ngx/paperless-ngx/blob/main/LICENSE)是 GNU GPL v3 文本。

借鉴原件、提取文本、索引分开的架构思路；本轮没有复制或链接其代码。若未来复用实现，需要按实际分发方式审查 GPL 条款，不能当作 MIT 项目处理。

## 本轮设计

保留现有离线轻量依赖，独立编写实现，没有复制上游源码或新增上游运行依赖。

- TextBlock 增加类型、标题级别、章节路径、嵌套表格坐标、PDF 页码；原有位置字符串和显示文字保持兼容。
- DOCX 使用直接/继承样式中的 outlineLvl 与 numPr，表格记录物理单元格路径；合并延续格不重复提取。表内标题不改变外层章节。
- TXT/PDF 仅保守识别 `#` 标题和“第…章/节”。普通数字列表不猜成标题，PDF 不凭字体猜版面。PDF 仍是一行一块。
- 唯一完整标题路径建立顺序锚点，区域内继续有上限的块匹配；标题文字变化仍形成差异。无可靠锚点时回退旧块算法。
- 连续 replace 仅在块数相等、类型及表格坐标一致、逐对词法相似度至少 0.45 且预算允许时细分。拆段、合段及不相关改写保留整个证据区域；最后生成字符级编辑范围。
- 章节区域共享块比较预算；细分判断也有字符预算。保留取消检查、粗匹配提示、原有移动识别与 Unicode 坐标。

0.45 是本轮启发式参数，仅控制显示分组，不决定文本是否有差异。标题重命名、重复标题、章节移动并改写仍可能退化成大范围替换，不能宣称完成了语义对齐或一般性结构差异识别。纯样式、列表显示编号、表格尺寸与合并形状不作为差异；页眉/脚注等原有限制保留。

## 版本识别评估与下一步

当前没有文档家族/最新候选功能。现有 Snapshot.sha256 是文件字节哈希，工作空间 cache_key 也是字节哈希加编码选择，不能充当跨格式内容指纹。

下一步先区分字节相同、提取正文相同、词法近似和包含四类；另建带解析器版本的正文指纹，保留原始字节摘要。小规模先用精确字符 shingles 建立基准，再评估 MinHash 的速度和候选召回。最新候选展示内部/文件时间、来源与缺失/并列情况，交由用户确认；模板共用、短文、附录包含、跨格式和复制时间漂移都要有验收案例。

## 全文检索评估与下一步

当前已经实现段落级 FTS5 trigram，三字符以上用 MATCH 后再字面验证，一两字符用 instr 回退；排序主要按文件名/命中频次，尚无字段 BM25、语义检索或自动监控。结构元数据暂不持久化进索引，缓存中的文字和位置不变，因此本轮无需升级索引版本。

下一步应先测 500 文档与总量上限下的扫描/搜索耗时和中文召回，再决定是否新增标题/章节索引、字段权重 BM25、显式筛选及增量更新。必须保留中文短词、标点和特殊引号的字面查询与原文跳转契约；不为“全文检索”名称另建一个重复后端。
