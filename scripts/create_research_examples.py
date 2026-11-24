"""Create four deterministic, synthetic research documents (no external papers)."""
from pathlib import Path

from docx import Document
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from doclens.research import ResearchProject


def create(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / '01-vision.md').write_text(
        '# Vision study (synthetic)\n## Methods\n😀 We use BERT on CIFAR10.\n'
        'We use ResNet-50 on ImageNet.\n## Related work\nPrevious papers discuss SVM and MNIST.\n', encoding='utf-8')
    (folder / '02-baseline.txt').write_text(
        'Methods\nWe use BERT on CIFAR-10.\nWe do not use ResNet.\n'
        'We use Random Forest on MNIST.\n', encoding='utf-8')
    doc = Document()
    doc.add_heading('Text study (synthetic)', 0)
    doc.add_heading('Methods', 1)
    doc.add_paragraph('We use BERT on SQuAD.')
    doc.add_paragraph('We do not use CNN.')
    doc.add_heading('Related work', 1)
    doc.add_paragraph('Prior work mentions CIFAR10 and ResNet.')
    doc.save(folder / '03-text.docx')
    writer = PdfWriter()
    page = writer.add_blank_page(612, 792)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
        NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
    stream = DecodedStreamObject()
    lines = ['Retrieval study (synthetic)', 'Methods', 'We use SVM on MNIST.',
             'We evaluate BERT on SQuAD.', 'We do not use ImageNet.']
    stream.set_data(('BT /F1 14 Tf ' + ' '.join(f'1 0 0 1 50 {740-i*30} Tm ({line}) Tj' for i, line in enumerate(lines)) + ' ET').encode('ascii'))
    page[NameObject('/Contents')] = writer._add_object(stream)
    writer.write(folder / '04-retrieval.pdf')
    project = ResearchProject('四篇合成论文对照')
    sources = sorted(p for p in folder.iterdir() if p.name[:2] in ('01', '02', '03', '04'))
    assert not project.import_files(sources)
    evidence = next(e for e in project.evidence() if e['term'] == 'BERT')
    project.save_note('', '四篇均出现 BERT，需逐条核对实际使用情境。ResNet 在部分论文仅为相关工作或明确未使用。', evidence['id'])
    project.save(folder / 'demo-project.json')
    project.export_bundle(folder / 'demo-share-without-originals.zip')
    (folder / 'demo-report.md').write_text(project.markdown(), encoding='utf-8')
    return project


if __name__ == '__main__':
    create(Path(__file__).resolve().parents[1] / 'examples' / '多文档研究')
