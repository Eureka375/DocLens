# 四篇合成论文对照

使用线索需人工核对；未发现不代表不存在。共享报告含提取正文和笔记。

| 类别 / 共同项 | 01-vision.md | 02-baseline.txt | 03-text.docx | 04-retrieval.pdf |
| --- | --- | --- | --- | --- |
| 数据集 / CIFAR-10（共同） | 使用线索 (1) | 使用线索 (1) | 仅提及或待核对 (1) | 未发现 (0) |
| 数据集 / ImageNet（共同） | 使用线索 (1) | 未发现 (0) | 未发现 (0) | 否定使用 (1) |
| 数据集 / MNIST（共同） | 仅提及或待核对 (1) | 使用线索 (1) | 未发现 (0) | 使用线索 (1) |
| 数据集 / SQuAD（共同） | 未发现 (0) | 未发现 (0) | 使用线索 (1) | 使用线索 (1) |
| 方法 / BERT（共同） | 使用线索 (1) | 使用线索 (1) | 使用线索 (1) | 使用线索 (1) |
| 方法 / CNN | 未发现 (0) | 未发现 (0) | 否定使用 (1) | 未发现 (0) |
| 方法 / Random Forest | 未发现 (0) | 使用线索 (1) | 未发现 (0) | 未发现 (0) |
| 方法 / ResNet（共同） | 使用线索 (1) | 否定使用 (1) | 仅提及或待核对 (1) | 未发现 (0) |
| 方法 / SVM（共同） | 仅提及或待核对 (1) | 未发现 (0) | 未发现 (0) | 使用线索 (1) |

## 笔记

四篇均出现 BERT，需逐条核对实际使用情境。ResNet 在部分论文仅为相关工作或明确未使用。
[关联证据](#e-f64a254de7559b35071cda84397167c243f85ce587eecf96f2e35a2b271d96e2-47-51-BERT)

## 证据

<a id="e-f64a254de7559b35071cda84397167c243f85ce587eecf96f2e35a2b271d96e2-55-62-CIFAR-10"></a>
**CIFAR-10 · 01-vision.md · 第 3 行 · 使用线索**

> 😀 We use BERT on CIFAR10.

<a id="e-f64a254de7559b35071cda84397167c243f85ce587eecf96f2e35a2b271d96e2-47-51-BERT"></a>
**BERT · 01-vision.md · 第 3 行 · 使用线索**

> 😀 We use BERT on CIFAR10.

<a id="e-f64a254de7559b35071cda84397167c243f85ce587eecf96f2e35a2b271d96e2-84-92-ImageNet"></a>
**ImageNet · 01-vision.md · 第 4 行 · 使用线索**

> We use ResNet-50 on ImageNet.

<a id="e-f64a254de7559b35071cda84397167c243f85ce587eecf96f2e35a2b271d96e2-71-80-ResNet"></a>
**ResNet · 01-vision.md · 第 4 行 · 使用线索**

> We use ResNet-50 on ImageNet.

<a id="e-f64a254de7559b35071cda84397167c243f85ce587eecf96f2e35a2b271d96e2-142-147-MNIST"></a>
**MNIST · 01-vision.md · 第 6 行 · 仅提及或待核对**

> Previous papers discuss SVM and MNIST.

<a id="e-f64a254de7559b35071cda84397167c243f85ce587eecf96f2e35a2b271d96e2-134-137-SVM"></a>
**SVM · 01-vision.md · 第 6 行 · 仅提及或待核对**

> Previous papers discuss SVM and MNIST.

<a id="e-db05347e08c5ff436770cd38046d5e9a3310385467c2d35f473610feec7bfce7-23-31-CIFAR-10"></a>
**CIFAR-10 · 02-baseline.txt · 第 2 行 · 使用线索**

> We use BERT on CIFAR-10.

<a id="e-db05347e08c5ff436770cd38046d5e9a3310385467c2d35f473610feec7bfce7-15-19-BERT"></a>
**BERT · 02-baseline.txt · 第 2 行 · 使用线索**

> We use BERT on CIFAR-10.

<a id="e-db05347e08c5ff436770cd38046d5e9a3310385467c2d35f473610feec7bfce7-47-53-ResNet"></a>
**ResNet · 02-baseline.txt · 第 3 行 · 否定使用**

> We do not use ResNet.

<a id="e-db05347e08c5ff436770cd38046d5e9a3310385467c2d35f473610feec7bfce7-79-84-MNIST"></a>
**MNIST · 02-baseline.txt · 第 4 行 · 使用线索**

> We use Random Forest on MNIST.

<a id="e-db05347e08c5ff436770cd38046d5e9a3310385467c2d35f473610feec7bfce7-62-75-Random Forest"></a>
**Random Forest · 02-baseline.txt · 第 4 行 · 使用线索**

> We use Random Forest on MNIST.

<a id="e-18b770005feca53ed5b976e147e6c7280e67305f252d9f6268faae4e5751f460-46-51-SQuAD"></a>
**SQuAD · 03-text.docx · 第 3 段 · 使用线索**

> We use BERT on SQuAD.

<a id="e-18b770005feca53ed5b976e147e6c7280e67305f252d9f6268faae4e5751f460-38-42-BERT"></a>
**BERT · 03-text.docx · 第 3 段 · 使用线索**

> We use BERT on SQuAD.

<a id="e-18b770005feca53ed5b976e147e6c7280e67305f252d9f6268faae4e5751f460-67-70-CNN"></a>
**CNN · 03-text.docx · 第 4 段 · 否定使用**

> We do not use CNN.

<a id="e-18b770005feca53ed5b976e147e6c7280e67305f252d9f6268faae4e5751f460-105-112-CIFAR-10"></a>
**CIFAR-10 · 03-text.docx · 第 6 段 · 仅提及或待核对**

> Prior work mentions CIFAR10 and ResNet.

<a id="e-18b770005feca53ed5b976e147e6c7280e67305f252d9f6268faae4e5751f460-117-123-ResNet"></a>
**ResNet · 03-text.docx · 第 6 段 · 仅提及或待核对**

> Prior work mentions CIFAR10 and ResNet.

<a id="e-4ec31b6d37de874dfc239db084fe246bc041f8e9393b61d0a8563da04f8f9a51-50-55-MNIST"></a>
**MNIST · 04-retrieval.pdf · 第 1 页 / 第 3 行 · 使用线索**

> We use SVM on MNIST.

<a id="e-4ec31b6d37de874dfc239db084fe246bc041f8e9393b61d0a8563da04f8f9a51-43-46-SVM"></a>
**SVM · 04-retrieval.pdf · 第 1 页 / 第 3 行 · 使用线索**

> We use SVM on MNIST.

<a id="e-4ec31b6d37de874dfc239db084fe246bc041f8e9393b61d0a8563da04f8f9a51-77-82-SQuAD"></a>
**SQuAD · 04-retrieval.pdf · 第 1 页 / 第 4 行 · 使用线索**

> We evaluate BERT on SQuAD.

<a id="e-4ec31b6d37de874dfc239db084fe246bc041f8e9393b61d0a8563da04f8f9a51-69-73-BERT"></a>
**BERT · 04-retrieval.pdf · 第 1 页 / 第 4 行 · 使用线索**

> We evaluate BERT on SQuAD.

<a id="e-4ec31b6d37de874dfc239db084fe246bc041f8e9393b61d0a8563da04f8f9a51-98-106-ImageNet"></a>
**ImageNet · 04-retrieval.pdf · 第 1 页 / 第 5 行 · 否定使用**

> We do not use ImageNet.

## 01-vision.md


- [# Vision study (synthetic)](#d-f64a254de7559b35071cda84397167c243f85ce587eecf96f2e35a2b271d96e2-0)
- [## Methods](#d-f64a254de7559b35071cda84397167c243f85ce587eecf96f2e35a2b271d96e2-1)
- [## Related work](#d-f64a254de7559b35071cda84397167c243f85ce587eecf96f2e35a2b271d96e2-4)

<a id="d-f64a254de7559b35071cda84397167c243f85ce587eecf96f2e35a2b271d96e2-0"></a>
# Vision study (synthetic)

<a id="d-f64a254de7559b35071cda84397167c243f85ce587eecf96f2e35a2b271d96e2-1"></a>
## Methods

<a id="d-f64a254de7559b35071cda84397167c243f85ce587eecf96f2e35a2b271d96e2-2"></a>
😀 We use BERT on CIFAR10.

<a id="d-f64a254de7559b35071cda84397167c243f85ce587eecf96f2e35a2b271d96e2-3"></a>
We use ResNet-50 on ImageNet.

<a id="d-f64a254de7559b35071cda84397167c243f85ce587eecf96f2e35a2b271d96e2-4"></a>
## Related work

<a id="d-f64a254de7559b35071cda84397167c243f85ce587eecf96f2e35a2b271d96e2-5"></a>
Previous papers discuss SVM and MNIST.

<a id="d-f64a254de7559b35071cda84397167c243f85ce587eecf96f2e35a2b271d96e2-6"></a>


## 02-baseline.txt


- [Methods](#d-db05347e08c5ff436770cd38046d5e9a3310385467c2d35f473610feec7bfce7-0)

<a id="d-db05347e08c5ff436770cd38046d5e9a3310385467c2d35f473610feec7bfce7-0"></a>
Methods

<a id="d-db05347e08c5ff436770cd38046d5e9a3310385467c2d35f473610feec7bfce7-1"></a>
We use BERT on CIFAR-10.

<a id="d-db05347e08c5ff436770cd38046d5e9a3310385467c2d35f473610feec7bfce7-2"></a>
We do not use ResNet.

<a id="d-db05347e08c5ff436770cd38046d5e9a3310385467c2d35f473610feec7bfce7-3"></a>
We use Random Forest on MNIST.

<a id="d-db05347e08c5ff436770cd38046d5e9a3310385467c2d35f473610feec7bfce7-4"></a>


## 03-text.docx


- [Methods](#d-18b770005feca53ed5b976e147e6c7280e67305f252d9f6268faae4e5751f460-1)
- [Related work](#d-18b770005feca53ed5b976e147e6c7280e67305f252d9f6268faae4e5751f460-4)

<a id="d-18b770005feca53ed5b976e147e6c7280e67305f252d9f6268faae4e5751f460-0"></a>
Text study (synthetic)

<a id="d-18b770005feca53ed5b976e147e6c7280e67305f252d9f6268faae4e5751f460-1"></a>
Methods

<a id="d-18b770005feca53ed5b976e147e6c7280e67305f252d9f6268faae4e5751f460-2"></a>
We use BERT on SQuAD.

<a id="d-18b770005feca53ed5b976e147e6c7280e67305f252d9f6268faae4e5751f460-3"></a>
We do not use CNN.

<a id="d-18b770005feca53ed5b976e147e6c7280e67305f252d9f6268faae4e5751f460-4"></a>
Related work

<a id="d-18b770005feca53ed5b976e147e6c7280e67305f252d9f6268faae4e5751f460-5"></a>
Prior work mentions CIFAR10 and ResNet.

## 04-retrieval.pdf


- [Methods](#d-4ec31b6d37de874dfc239db084fe246bc041f8e9393b61d0a8563da04f8f9a51-1)

<a id="d-4ec31b6d37de874dfc239db084fe246bc041f8e9393b61d0a8563da04f8f9a51-0"></a>
Retrieval study (synthetic)

<a id="d-4ec31b6d37de874dfc239db084fe246bc041f8e9393b61d0a8563da04f8f9a51-1"></a>
Methods

<a id="d-4ec31b6d37de874dfc239db084fe246bc041f8e9393b61d0a8563da04f8f9a51-2"></a>
We use SVM on MNIST.

<a id="d-4ec31b6d37de874dfc239db084fe246bc041f8e9393b61d0a8563da04f8f9a51-3"></a>
We evaluate BERT on SQuAD.

<a id="d-4ec31b6d37de874dfc239db084fe246bc041f8e9393b61d0a8563da04f8f9a51-4"></a>
We do not use ImageNet.
