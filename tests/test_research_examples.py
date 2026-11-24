import importlib.util
from pathlib import Path

from doclens.research import ResearchProject


def test_four_format_acceptance_corpus(tmp_path):
    path = Path(__file__).resolve().parents[1] / 'scripts/create_research_examples.py'
    spec = importlib.util.spec_from_file_location('examples_generator', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    p = module.create(tmp_path)
    assert len(p.documents) == 4
    rows = {r['term']: r for r in p.matrix()}
    assert [c['state'] for c in rows['BERT']['cells']] == ['使用线索'] * 4
    assert [c['state'] for c in rows['ResNet']['cells']] == ['使用线索', '否定使用', '仅提及或待核对', '未发现']
    assert [c['state'] for c in rows['CIFAR-10']['cells']] == ['使用线索', '使用线索', '仅提及或待核对', '未发现']
    shared = ResearchProject.load(tmp_path / 'demo-share-without-originals.zip')
    assert shared.notes == p.notes and shared.matrix() == p.matrix()
