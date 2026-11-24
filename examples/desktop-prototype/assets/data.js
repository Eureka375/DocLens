/* All research content is synthetic demonstration data. */
window.DEMO = {
 project: '视觉表征学习 · 文献综述',
 docs: [
 {id:'a',name:'01_对比表征研究.pdf',short:'对比表征研究',format:'PDF',status:'解析完成',title:'Contrastive representations for visual learning',subtitle:'对比表征研究 · 合成研究文档 A',text:'本示例研究视觉表征的训练与评测流程。\n我们在 CIFAR-10 上进行评测，并采用 ResNet 作为编码器。\n训练过程包含数据增强与对比学习目标。\n相关工作提及 Transformer，但本文未开展相关实验。'},
 {id:'b',name:'02_轻量视觉编码.docx',short:'轻量视觉编码',format:'DOCX',status:'解析完成',title:'Efficient visual encoding with limited data',subtitle:'轻量视觉编码 · 合成研究文档 B',text:'本示例研究资源受限条件下的编码策略。\n相关工作讨论了 CIFAR-10，本文实验使用另一个合成集合。\n本研究采用 ResNet 作为基线编码器。\n关于 Transformer 的描述缺少实验主体，无法确认使用情况。'},
 {id:'c',name:'03_注意力基线.md',short:'注意力基线',format:'MD',status:'解析完成',title:'An attention baseline for visual comparison',subtitle:'注意力基线 · 合成研究文档 C',text:'本示例评估注意力编码器的比较方式。\n我们使用 CIFAR-10 评测 Transformer 编码器。\n本研究未使用 ResNet，采用独立注意力基线。\n所有数值与研究结论仅为演示，不代表真实实验。'},
 {id:'d',name:'04_待整理观察.txt',short:'待整理观察',format:'TXT',status:'部分提取',title:'Preliminary observations',subtitle:'待整理观察 · 合成研究文档 D',text:'本示例包含一份尚未整理完整的观察记录。\n提取片段出现 Transformer，但上下文不足。\n部分内容在本演示中不可用，不能据此断言不存在某种方法。'}
 ],
 rows:[
 {name:'CIFAR-10',dim:'数据集',states:['使用线索','仅提及','使用线索','未发现'],quotes:[1,1,1,-1]},
 {name:'ResNet',dim:'方法',states:['使用线索','使用线索','明确未使用','未发现'],quotes:[1,2,2,-1]},
 {name:'Transformer',dim:'方法',states:['仅提及','证据不足','使用线索','证据不足'],quotes:[3,3,1,1]}
 ]
};
