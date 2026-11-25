/* Synthetic documents and scripted AI examples, for interface review only. */
window.DEMO = {
    project: '视觉表征学习文献综述',
    keywords: ['ResNet', 'CIFAR-10', '训练轮数'],
    documents: [
        {
            id: 'a', name: '对比表征研究.pdf', format: 'PDF', status: '解析完成',
            blocks: [
                {section: '1 引言', location: '第 1 页 · 段落 1', text: '本示例研究视觉表征的训练与评测流程，目标是比较不同编码器的实验设置。'},
                {section: '2 实验设置', location: '第 2 页 · 段落 3', text: '本研究使用 ResNet 作为视觉编码器，在 CIFAR-10 上训练 50 轮。评估采用固定随机种子，报告三次实验的均值。', verdict: '本文采用', reason: '本文明确用 ResNet 作为视觉编码器，并在 CIFAR-10 上训练。'},
                {section: '3 结果', location: '第 4 页 · 段落 2', text: 'ResNet 的结果按训练轮数分组。ResNet 与注意力基线共享相同的验证集。'},
                {section: '3 结果', location: '第 4 页 · 段落 3', text: '附录另列 ResNet50 和 ResNet-50 的参数设置。'}
            ]
        },
        {
            id: 'b', name: '轻量视觉编码.docx', format: 'DOCX', status: '解析完成',
            blocks: [
                {section: '1 引言', location: '段落 1', text: '本示例关注资源受限场景中的轻量视觉编码。'},
                {section: '2 相关工作', location: '段落 2', text: '相关工作使用 ResNet 作为视觉编码器，在 CIFAR-10 上训练 100 轮。评估采用固定随机种子，报告三次实验的均值。', verdict: '背景或相关工作提及', reason: '句子的主体是相关工作。100 轮是引述的设置，不能归为本文实验。'},
                {section: '3 本文方法', location: '段落 3', text: '本文实验采用轻量注意力编码器，训练轮数为 75。'}
            ]
        },
        {
            id: 'c', name: '注意力基线.md', format: 'MD', status: '解析完成',
            blocks: [
                {section: '1 实验目标', location: '段落 1', text: '本示例比较注意力编码器与轻量结构。'},
                {section: '2 方法', location: '段落 2', text: '本研究未采用 ResNet，而使用独立注意力编码器。', verdict: '明确未采用', reason: '本文直接写明未采用 ResNet，并指出替代编码器。'},
                {section: '3 数据', location: '段落 3', text: '我们在 CIFAR-10 上评测注意力基线。', verdict: '本文采用', reason: '正文明确说本文在 CIFAR-10 上评测。'}
            ]
        },
        {
            id: 'd', name: '待整理观察.txt', format: 'TXT', status: '部分提取',
            blocks: [
                {section: '实验记录片段', location: '段落 1', text: '剩余片段只写了 ResNet 与参数设置。上下文缺失，无法判断哪篇研究采用了它。', verdict: '无法确定', reason: '可用片段缺少实验主体，且文档部分提取。'},
                {section: '实验记录片段', location: '段落 2', text: '待整理：核对原稿中的数据集和实验记录。'}
            ]
        }
    ]
};
