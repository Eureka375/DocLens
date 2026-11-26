/* Synthetic research material. This is not a factual claim about real papers. */
window.DOC_DEMO = [
  {id:'a', title:'小样本视觉表征研究', author:'陈予安 等', year:'2025', format:'PDF', color:'violet', sections:[
    {title:'摘要', text:'本文研究有限标注条件下的视觉表征学习，关注特征迁移与训练资源之间的平衡。'},
    {title:'3.1 数据与实验设置', text:'We evaluate our encoder on CIFAR-10. We use ResNet-50 as the backbone and train it for 50 epochs. The input resolution is 32 × 32 pixels. All experiments use a batch size of 128.'},
    {title:'4.2 主要结果', text:'Under the stated experimental setting, the classification accuracy reaches 91.5%. This result is reported only for CIFAR-10 and should not be directly compared with results on other datasets.'},
    {title:'5 研究局限', text:'The evaluation is limited to small-resolution images. We have not tested the encoder on high-resolution data or measured its deployment latency.'}
  ]},
  {id:'b', title:'轻量视觉编码与迁移', author:'林知远 等', year:'2025', format:'DOCX', color:'blue', sections:[
    {title:'摘要', text:'本文探索适用于资源受限设备的视觉编码方法，通过知识迁移降低部署成本。'},
    {title:'2 相关工作', text:'Prior work used ResNet-50 on CIFAR-10 and trained the model for 100 epochs. These settings belong to the cited study, not to our experiments.'},
    {title:'3.2 实现细节', text:'We use MobileNetV3 as our encoder and evaluate it on CIFAR-100. Our model is trained for 80 epochs. We do not use ResNet-50 in our experiments.'},
    {title:'5 研究局限', text:'The deployment latency has not yet been measured on real mobile hardware. Accuracy values depend on the chosen dataset and training setting.'}
  ]},
  {id:'c', title:'自监督表征的对照实验', author:'周以宁 等', year:'2026', format:'MD', color:'teal', sections:[
    {title:'研究问题', text:'我们研究自监督表征与监督基线在同一数据集上的差异，重点控制训练预算。'},
    {title:'3 实验配置', text:'We evaluate a ResNet-50 encoder on CIFAR-10. The encoder is trained for 200 epochs with a batch size of 256. The baseline is evaluated under the same data split.'},
    {title:'4 结果与讨论', text:'The measured accuracy is 93.2% under our own protocol. Differences in training duration mean that this number alone does not establish superiority over other studies.'},
    {title:'5 研究局限', text:'Additional experiments on larger datasets and multiple random seeds are needed. The study does not provide energy consumption measurements.'}
  ]},
  {id:'d', title:'文献阅读与比较备忘', author:'我的资料', year:'2026', format:'TXT', color:'gray', sections:[
    {title:'阅读提示', text:'比较实验结果时，应同时检查数据集、模型、训练轮次和评价协议。相同名称的出现不等于本文实际采用。'},
    {title:'待办', text:'检查三篇材料的训练设置，并将原文证据保存到同一条研究笔记。'}
  ]}
];
window.MATRIX_DEMO = [
  {id:'dataset', title:'数据集', type:'实体', values:['CIFAR-10','CIFAR-100','CIFAR-10'], blocks:[1,2,1], status:['明示','明示','明示']},
  {id:'backbone', title:'骨干网络', type:'实体', values:['ResNet-50','MobileNetV3','ResNet-50'], blocks:[1,2,1], status:['明示','明示','明示']},
  {id:'epochs', title:'训练轮次', type:'数值', values:['50 epochs','80 epochs','200 epochs'], blocks:[1,2,1], status:['明示','明示','明示']},
  {id:'accuracy', title:'分类准确率', type:'数值', values:['91.5%','未找到','93.2%'], blocks:[2,null,2], status:['明示','未找到','明示']},
  {id:'limits', title:'研究局限', type:'文本', values:['仅小分辨率图像','未测真实移动设备','需更多数据集与随机种子'], blocks:[3,3,3], status:['概括，待验证','概括，待验证','概括，待验证']}
];
