# DocLens 技术设计方案

版本：1.0 · 2026-11-26 · 状态：总体方向已确认，详细实现候选、待代码审查及 PoC。

依据：[需求规格](requirements.md)及用户补充的八阶段完整汇总。验证：[PoC方案](poc-plan.md)；执行：[开发计划](../superpowers/plans/development-plan.md)。本稿不是已实施架构或实测报告。

## 1. 确认方向与选型边界

已确认九项：传统算法/Embedding/LLM混合；统一结构及原文映射；SQLite FTS5+本地向量；四级关联；检索增强结构化提取；本地4B/8B量化优先测试；可选外部模型；沿用现有工程及版本比对；五组PoC后正式开发。

IDE工作台、任务驱动、证据共用、本地优先为产品约束。具体语言库、版本、运行时、模型、数据库schema和接口为候选。当前仅查阅README和部分设计，没有审查main源码或执行测试；不能据文档锁定复用比例。

## 2. 分层架构与模块责任

- **用户交互层**：IDE工作台，文档阅读、矩阵、关联展示、研究笔记、设置。最左功能、左资源、中央工作区、顶部标签、右证据/章节/笔记、底部任务状态；面板可折叠/调宽/关闭。
- **业务服务层**：ProjectService、DocumentService、TaskService、ResultService、NoteService、ExportService。负责项目与任务范围、持久化、转换、结果生命周期及授权。
- **核心分析层**：SearchService、DiscoveryService、ExtractionService、VersionDiffer、EvidenceService。只依赖稳定契约，不直接控制界面。
- **基础能力层**：Parser、SectionRecognizer、TextMatcher、Embedder、EntityExtractor、ModelProvider及索引适配器。
- **本地数据层**：SQLite、FTS5、本地向量文件/索引、原文件或引用、解析快照、缓存、结果与笔记。

数据主链：导入→解析/章节→不可变快照与映射→Chunk→全文/向量索引→检索或四级关联→维度提取/矩阵→证据校验与人工核对→记录/笔记→MD/CSV/分享包。Diff以两个文档版本为输入并输出两侧证据；可从临时快速分析入口进入。

传统算法处理确定性匹配、Diff和结构校验；Embedding处理召回与主题候选；LLM处理开放实体、语境、结构化提取等。能够由传统或轻量方案可靠完成的任务不强制LLM。

## 3. 候选技术栈与决策依据

以下保留原汇总中的候选名称，未核查最新发布、可获取性、模型许可或具体API，不视作已锁定依赖：

- 桌面/前端/构建：优先沿用现有框架与组件；README描述Python/PySide6/QML，须main审查证实。
- 核心算法Python；数据校验Pydantic；自动化pytest。
- 解析：现有解析器、Docling、pdfplumber；扩展评估PyMuPDF时先核查AGPL/商业许可兼容性。
- PDF阅读：现有组件或PDF.js；是否适配桌面及坐标同步需验证，不默认更换。
- SQLite元数据与FTS5；小规模NumPy精确向量优先，必要时FAISS。不部署独立向量数据库服务。
- Embedding：BGE-M3、BGE-small系列；运行Sentence Transformers；可选ONNX Runtime做CPU优化。
- 可选重排：BGE-reranker-v2-m3。
- 聚类：scikit-learn、HDBSCAN；主题TF-IDF/c-TF-IDF与可选LLM命名。
- 本地生成：Qwen3-4B-Instruct-2507、Qwen3-8B量化候选；名称/实际制品须核对，不凭名称推定可用。运行候选Ollama或llama.cpp。
- 可视化：ECharts等，先满足基础列表/分组；高级关系图后续。
- 笔记Markdown编辑器；矩阵标准CSV库；ZIP+JSON清单分享；Windows系统凭据保护密钥。

暂不引入Redis、MySQL、Kafka、微服务及独立向量数据库服务。选型按质量、证据能力、资源/时延、Windows分发、维护成本、许可比较，保留否决理由及回退方案。

## 4. 统一数据模型与版本关系

以下是候选字段设计，必须在DEV-01/02固化schema与迁移契约：

- **Project**：id、名称/说明、schemaVersion、文档与任务集合、最近保存点。
- **Document**：稳定逻辑ID、格式、来源（敏感本地字段）、版本集合、当前版本、标签/基础组织。
- **DocumentVersion**：versionId、documentId、文件SHA-256、导入时间、解析器及版本、状态、警告、可选旧源副本。文件散列用于变化识别，不把路径当身份。
- **Section**：id、versionId、父节点、标题、层级、顺序、源位置。
- **ContentBlock**：document_id、document_version、block_id、section_path、page、text、bbox、block_type、字符偏移、文件哈希、解析器版本。不存在的页码/bbox明确为空。
- **Chunk**：chunkId、文本、多个ContentBlock来源区间、检索归一化到原文的映射、分块规则版本；检索Chunk不冒充原始块。
- **AnalysisTask**：id、类型/模式、文档版本集合、维度/查询/参数、来源任务、状态、阶段、进度、失败项、取消标记、索引及模型版本。
- **AnalysisResult**：id、runId、输出与覆盖、证据ID、生成时间、机器结果、人工修订、过期原因；不可因新运行覆盖旧run。
- **Evidence**：id、document/version/block、半开区间、quote、章节/页/bbox、映射质量、真实性/定位校验、支持性评估与失效原因；一个结论可有多条多来源证据。
- **Entity**：规范ID/名、类型、别名、原始提及、上下文角色、实体链接/消歧依据；名称不限词典。
- **Note**：id、Markdown、证据/结果关联、创建/修改时间、保存版本；≤5秒未保存窗口。
- **IndexGeneration**：快照集合、tokenizer、Chunk规则、Embedding模型/维度/归一化/距离、构建状态、发布时间。

索引是可重建派生数据，人工笔记及历史结果是持久成果，清理不得混同。DocumentVersion与结果版本分开；未保存旧源时不保证历史原貌可打开，但必须保存历史结果并标失效。

## 5. 来源映射与解析接口

候选统一接口：`Parser.parse(source, options, taskContext) -> ParsedDocument`，输出版本、ContentBlock、Section、警告与统计；支持按文档失败、进度及取消检查点。

PDF以真实页码/文字块/页面坐标定位；DOCX以标题、段落、表格位置；Markdown以标题路径/行号/字符偏移；TXT以行号/字符偏移。Markdown转换不能丢失源映射，也不替代原始PDF阅读。

建议后端区间统一Unicode码点`[start,end)`，UI边界转UTF-16；需覆盖emoji、中文、组合字符和重复句。PDF坐标契约明确页面尺寸、旋转、缩放及原点；建议内部以未缩放页面左上原点记录，适配器保留原坐标变换；最终契约由E01确认。

归一化、分块、去页眉及拼接必须保留逆映射。部分提取和无法定位不得伪成功。组合解析器只在有独立证据与稳定位置时采用，不能混合文本后丢来源。文本PDF为P0，OCR P1；DOCX基础表格可用，复杂公式/图像/版式明确提示。

## 6. 检索接口与索引生命周期

候选接口：

- `KeywordIndex.build(versions, config, context) -> generation`。
- `KeywordIndex.query(query, scope, sort, limit) -> SearchHit[]`。
- `Embedder.encode(texts, purpose) -> vectors + modelFingerprint`。
- `VectorIndex.build/search(vector, scope, k) -> candidates`。
- `SearchService.search(request) -> hits + coverage + indexState + timings`。

SearchHit包含文档版本、Chunk、原始块映射、片段/上下文、分数及证据定位。不同模式分数含义分开，不作为结论可信度。

### 6.1 关键词

已确认SQLite FTS5，候选BM25、中文分词或字符级索引、trigram及不足3字符回退。FTS5存在不代表短中文、标点、术语边界自然正确；E02专测一/二字、英文缩写、CIFAR-10/100等正反例。跨项目/分组/文档范围过滤不可泄漏其他来源。

### 6.2 语义与混合

查询Embedding→NumPy精确相似度基线→可选FAISS→候选融合RRF→可选重排→去重与可定位结果。MVP规模先证明精确搜索满足质量/时延，再评估复杂索引。关键词/语义均必需；混合和重排作为E02对照，由证据选择。

模型、维度或Chunk规则变更需重建相应向量，不混用。新索引代次构建完成再发布；失败保留旧代次并显示过期状态。计时包含查询向量、融合/重排及结果交付，加载/冷启动单列；正式边界按D01冻结。目标ACC03/04与500ms/2秒不能因重排而自动放宽。

## 7. 四级关联接口

`DiscoveryService.discover(versionIds, mode, relationTypes, options, context) -> groups + relations + evidence + coverage`。自动模式由系统主动发现，定向模式由用户指定类型；每级单独评估，不用实体指标替全部。

- **L1相同文本**：文本标准化、段落/N-gram、SHA-256/Rolling Hash、聚合、原文验证；过滤页眉、参考文献、版权、模板。标准化相同与原始逐字相同区分。
- **L2相似内容**：Embedding跨文档候选、阈值、可选重排/语义判断、分组及双侧证据。避免全段落LLM两两比较，保留“表达相似但含义不同”负例。
- **L3共同实体**：开放提取→类型→名称归一→上下文消歧→语义角色→跨文档聚合。类型可预设，实体名称不限词库；CIFAR-10/100、ResNet-50/101不误合。区分实际使用、对照实验、相关工作提及、明确否定、无法判断。
- **L4基础主题**：Embedding+HDBSCAN/层次聚类，TF-IDF/c-TF-IDF关键词，可选LLM命名；一个文档可多主题，不强制唯一归类。主题链接成员与证据，复杂观点冲突分析后置。

返回用户可确认/删除/修正的关联及原机器结果，不覆盖审计来源。定向10篇≤60秒，自动发现单列耗时且阈值待决。

## 8. 检索增强结构化提取接口

`ExtractionService.extract(versionIds, dimensions, modelPolicy, context) -> MatrixResult`。

维度定义：字段ID、名称/说明、类型、单位与多值/缺失规则。流程：维度转检索目标→逐篇召回→证据不足时有界扩大范围/完整章节→LLM结构提取→JSON Schema/Pydantic校验→原文校验→矩阵→人工验证。

输出至少`document_id, field, value, unit, status, evidence[]`；每条证据含真实block_id、quote及来源。校验类型、ID、范围、逐字一致、数值与单位合理性；不悄悄“修复”不存在的引文。结论支持性独立核对。

状态区分明示、推断、未找到、歧义、冲突、不适用、解析失败、证据失效、人工确认/修正。缺失不填造，不因跨数据集/实验条件的指标差异宣称方法优劣。记录检索覆盖、截断与未处理字段，防止只统计成功字段。

MVP支持基础模板、自定义维度、矩阵/共同点/差异、编辑、保存导出；增量只补新文档/维度为正式版能力，接口预留但不声称MVP已做。

## 9. 统一证据服务

候选接口：`create/validate/resolve/invalidate/review`；Evidence由后端管理而非模型自由生成字符串。

验证链：文档版本存在→ContentBlock存在→引用逐字真实→结论支持性评估→真实位置可跳转→无效则拒绝、重提或待确认。结构校验不能证明语义支持；推断保留标签。有效引用与定位100%，同时报告无效拒绝与证据覆盖以避免空集达标。

所有SearchHit、关联、矩阵、Diff、笔记共享版本身份。历史版本缺失明确失效；更新不能把旧证据重绑到新版本近似文字。人工确认/否定/修正与机器字段分开，任务转换复用稳定ID。

## 10. 任务状态机、更新与恢复

对用户状态：待执行→执行中→已完成/执行失败/已取消；已完成→待更新或已归档；待更新→用户发起新运行；已取消/失败→用户重启/重试。内部可增加取消中和部分完成，不替代已确认用户状态。

Worker线程/独立进程处理耗时任务，UI可操作；按阶段/块报告进度和检查取消；单次不可中断调用需在实测报告中说明取消延迟。失败项隔离，重试只补失败项；重新分析产生新run并保存旧成果。

任务状态持久化；异常重启识别中断并支持用户重试，不自动重发外部请求。取消不撤回已发送远端内容，重试可能重复计费；授权范围变化或服务变化需重新确认。并发可配置，数据库写入集中管理。

基础变化检测以哈希/版本记录实现。建议打开项目或显式刷新时检查，实际触发协议待决；发现变化标记索引/结果过期、证据受影响，用户决定更新。实时监控及高级增量后置，不能以此省掉MVP基础检测。

SQLite事务、版本化迁移、临时文件原子替换、恢复日志/基本备份为候选策略；外部文件与向量索引不天然同一事务，采用代次+manifest发布协议。笔记自动保存≤5秒；保存失败保留草稿与上一份可读成果，不能显示已保存。

## 11. 模型适配、资源与授权

`ModelProvider.capabilities/generate/cancel/usage`统一模型标识、结构输出能力、上下文限额、超时、错误及Token/资源统计。本地与外部适配器均返回结构结果和来源；不因本地失败静默转云。

首轮BGE-M3、小模型对照及4B量化；第二轮重排、8B量化，可选已授权云对照。资源权重理论值：4B 4bit约1.86GiB，8B 4bit约3.73GiB，14B 4bit约6.52GiB，4B FP16约7.45GiB；只是参数位数估算，不含KV Cache、缓冲和量化附加数据，不推导实际显存或速度。

软件空闲≤500MB、CPU≤2%，基础分析峰值≤2GB（模型另计）；开发者自述31.71GB/RTX4060 Laptop，实际显存须检测。普通无独显Windows基础流程必测，本地语义优先CPU可用；复杂提取离线能力由PoC决定并显式告知。

外传前展示服务、模型、实际片段及上下文、范围/排除、用量/估算；凭据由Windows账户保护机制保存，不进入项目/包/日志。授权绑定内容与接收方，重试范围另定。本地模式拦截外传；模型下载是安装行为，不混入已建索引时延。

## 12. 导出、分享与安全

MVP：Markdown笔记/报告、CSV矩阵、ZIP+JSON基础包导入导出。候选包包含manifest/schema、成果与来源快照、MD/CSV、可选原文件。是否带源及本地路径必须预览；默认省略个人绝对路径，是否包含原文件显式选择。即使无原文件，提取正文/引文也可能敏感。

先验证schema、散列、证据、条目及解压限额，再原子导入新项目；拒绝路径穿越、重复项、恶意压缩包、未知不兼容版本、越界证据、不可信代码执行。失败不损坏当前项目。旧项目迁移保留备份，未知版本拒绝或只读处理策略待D09。

文档与模型输出只当数据；不可信指令不得改变系统命令、读取范围或授权。日志记录任务ID、阶段、耗时、错误码，不默认正文、密钥及个人路径。数据清理区分项目派生内容与用户源文件。

## 13. 接口错误契约与工程复用

候选共用错误码：`UNSUPPORTED_FORMAT`、`PARSE_PARTIAL/FAILED`、`CANCELLED`、`INDEX_STALE/CORRUPT`、`SOURCE_VERSION_MISSING`、`EVIDENCE_INVALID`、`MODEL_UNAVAILABLE`、`SCHEMA_INVALID`、`AUTH_REQUIRED`、`BUDGET_EXCEEDED`、`STORAGE_FAILED`、`PACKAGE_INVALID`。返回是否可重试、受影响项与用户可操作提示；错误不退化为“未找到”。

AUD-01审查main确切commit、现有解析/结构Diff/定位/AI授权/存储/构建/测试。逐模块输出复用、适配、替换、缺失及原因。先固定现有回归样例，再把旧模块接入新契约；旧双栏、临时比对与已验证功能保留。迁移旧JSON/缓存的方案取决于审查，不假设已采用SQLite项目库。

## 14. 风险、参考与决策记录

主要风险：多栏PDF阅读顺序和坐标漂移；中文短词；开放实体误合与引用主体混淆；主题不稳定；检索漏召回；字段空值虚高；4B/8B资源或质量不达标；历史证据失效；跨存储半写入；分享恶意包；旧项目兼容；许可与模型分发。

待决以SRS D01–D09为准；选择记录须含候选版本/许可、数据与硬件、质量/时延/资源、失败例、选择及回退理由。未过门槛保持候选，不降低指标。

原需求给出的开源参考（本次未做仓库或许可证实查）：[Docling](https://github.com/docling-project/docling)、[pdfplumber](https://github.com/jsvine/pdfplumber)、[FlagEmbedding](https://github.com/FlagOpen/FlagEmbedding)、[PaperQA2](https://github.com/Future-House/paper-qa)、[LightRAG](https://github.com/HKUDS/LightRAG)、[PDF.js](https://github.com/mozilla/pdf.js)、[Zotero](https://github.com/zotero/zotero)、[ColPali](https://github.com/illuin-tech/colpali)。分别参考解析、检索/重排、引用、实体、阅读笔记；ColPali属后续视觉研究。引用或复用前核对确切版本及许可证，候选名称不构成采纳结论。