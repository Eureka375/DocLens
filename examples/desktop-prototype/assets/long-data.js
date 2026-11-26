/* Synthetic research records with chapter structure and repeatable experiments. */
(() => {
    const chapters = [
        ['研究问题', '研究目标', '从复现难度、训练成本和样本质量三个角度界定实验范围。'],
        ['数据与划分', '样本划分', '将训练集与验证集独立保存，避免同一来源的近重复样本跨集合出现。'],
        ['数据清洗', '质量抽检', '记录重复、低清晰度和标签存疑的条目，并保留审阅记录。'],
        ['输入预处理', '变换顺序', '按固定顺序读取、缩放和归一化图像，保留原始尺寸供复查。'],
        ['编码器结构', '特征分布', '从相同层提取表示，并记录特征维度与推理时的峰值内存。'],
        ['训练协议', '训练稳定性', '在同一预算下比较不同训练轮数，逐次保存学习曲线和最终权重。'],
        ['评价指标', '指标计算', '分别汇总整体和按类别统计的结果，并记录置信区间的计算方式。'],
        ['对照实验', '主对照', '两组实验共用固定样本划分，以便直接核对设置和测量结果。'],
        ['消融分析', '变量隔离', '每次只替换一项配置，其他输入沿用对应实验的基准设置。'],
        ['失败案例', '误差来源', '按低照度、遮挡和背景相似性划分失败样本，再交由人工核对。'],
        ['复现记录', '复现条件', '保存依赖版本、数据摘要与随机种子，以便复核同一次实验。'],
        ['附录与补充结果', '补充记录', '整理正文未展开的实验日志，标出应优先阅读和复核的条目。']
    ];
    const slices = ['室内', '室外', '高对比度', '低对比度', '背景复杂', '背景简单', '中等尺寸', '小尺寸', '远距离'];
    const methods = ['留出集复核', '重新抽样', '固定划分复跑', '检查点回读', '盲审复核', '曲线回溯'];

    function makeDocument(id, name, ownExperiment) {
        const blocks = chapters.flatMap(([title, focus, guidance], chapter) =>
            Array.from({length: 24}, (_, index) => {
                const round = chapter === 7 && index === 3 ? (ownExperiment ? 50 : 100) : 30 + (chapter + index) * 5;
                const seed = 110 + chapter * 24 + index + (ownExperiment ? 0 : 300);
                const slice = slices[(index + chapter) % slices.length];
                const method = methods[(chapter + index) % methods.length];
                const subject = ownExperiment ? '本研究' : '相关工作';
                const record = `第 ${chapter + 1} 组记录 ${index + 1}。本段核对${slice}场景的${focus}，采用${method}，随机种子为 ${seed}。${guidance}本记录附有示意数据，结果仅用来演示长文档中的定位、比较与引用。`;
                const marker = index === 3 || index === 11 || index === 19;
                const report = `${subject}使用 ResNet 作为编码器，在 CIFAR-10 上训练 ${round} 轮。评估采用固定划分，报告三次实验的均值。`;
                const text = marker ? `${report}${record}` : record;
                return {
                    section: `${chapter + 1} ${title}`,
                    location: `正文段落 ${chapter * 24 + index + 1}`,
                    text,
                    ...(marker ? {
                        verdict: ownExperiment ? '本文采用' : '背景或相关工作提及',
                        reason: ownExperiment ? '所选片段描述本文的训练设置。' : '所选片段明确在转述相关工作。'
                    } : {})
                };
            })
        );
        return {id, name, format: 'MD', status: '解析完成', blocks};
    }

    const exampleBlock = 7 * 24 + 3;
    window.LONG_DEMO = {
        project: '视觉编码实验 · 长文档案例',
        keywords: ['ResNet', 'CIFAR-10', '复现条件'],
        documents: [
            makeDocument('a', '视觉编码实验记录A.md', true),
            makeDocument('b', '视觉编码文献记录B.md', false)
        ],
        pair: [`a:${exampleBlock}`, `b:${exampleBlock}`],
        summary: '两条选中证据的训练轮数不同。A 描述本文实验，B 转述相关工作。'
    };
})();
