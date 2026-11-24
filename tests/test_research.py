import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from doclens.research import ResearchProject


def corpus(tmp_path):
    a = tmp_path / 'a.md'
    a.write_text('# Methods\n😀 We use BERT on CIFAR10.\n# Related work\nResNet uses ImageNet.', encoding='utf-8')
    b = tmp_path / 'b.txt'
    b.write_text('We use BERT on CIFAR-10. We do not use ResNet.', encoding='utf-8')
    c = tmp_path / 'c.txt'
    c.write_text('Related work mentions BERT.\nWe use SVM.', encoding='utf-8')
    return [a, b, c]


def test_matrix_evidence_and_partial_batch(tmp_path):
    p = ResearchProject('研究')
    paths = corpus(tmp_path)
    bad = tmp_path / 'bad.docx'
    bad.write_bytes(b'broken')
    issues = p.import_files([*paths, bad, paths[0]])
    assert len(p.documents) == 3 and len(issues) == 2
    rows = {r['term']: r for r in p.matrix()}
    assert rows['CIFAR-10']['common']
    assert [c['state'] for c in rows['BERT']['cells']] == ['使用线索', '使用线索', '仅提及或待核对']
    assert rows['ResNet']['cells'][0]['state'] == '仅提及或待核对'
    assert rows['ResNet']['cells'][1]['state'] == '否定使用'
    assert rows['CIFAR-10']['cells'][2]['state'] == '未发现'
    for e in p.evidence():
        d = p.document(e['document'])
        assert d['text'][e['start']:e['end']] == e['quote']
    assert p.documents[0]['blocks'][0]['kind'] == 'heading'


@pytest.mark.parametrize('originals', [False, True])
def test_project_notes_and_offline_roundtrip(tmp_path, originals):
    p = ResearchProject('共享')
    p.import_files(corpus(tmp_path))
    e = p.evidence()[0]
    n = p.save_note('', '核对数据', e['id'])
    p.save_note(n, '已核对数据', e['id'])
    target = tmp_path / 'project.json'
    p.save(target)
    restored = ResearchProject.load(target)
    assert restored.notes == p.notes
    bundle = tmp_path / 'share.zip'
    restored.export_bundle(bundle, originals)
    shared = ResearchProject.load(bundle)
    assert shared.matrix() == p.matrix() and shared.notes == p.notes
    with ZipFile(bundle) as z:
        assert bool([n for n in z.namelist() if n.startswith('originals/')]) == originals
        assert str(tmp_path).encode() not in z.read('project.json')
    report = p.markdown()
    assert '已核对数据' in report and '(#e-' in report and '<a id="e-' in report
    restored.remove_document(e['document'])
    assert restored.notes[0]['evidence'] == ''
    restored.delete_note(n)
    assert not restored.notes


def test_invalid_share_and_tampered_evidence_are_rejected(tmp_path):
    p = ResearchProject('safe')
    p.import_files(corpus(tmp_path))
    f = tmp_path / 'project.json'
    p.save(f)
    data = json.loads(f.read_text(encoding='utf-8'))
    data['documents'][0]['blocks'][0]['start'] = -1
    f.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError):
        ResearchProject.load(f)
    z = tmp_path / 'bad.zip'
    with ZipFile(z, 'w') as archive:
        archive.writestr('../project.json', '{}')
    with pytest.raises(ValueError):
        ResearchProject.load(z)


def test_entity_boundaries_and_mixed_clauses(tmp_path):
    f = tmp_path / 'mixed.md'
    f.write_text('# Methods\nBERTology is a word.\nWe use BERT but do not use CNN.\nBERT and ResNet are discussed.\nWe use BERT instead of ResNet.', encoding='utf-8')
    p = ResearchProject('mixed')
    p.import_files([f])
    es = p.evidence()
    assert len([e for e in es if e['term'] == 'BERT']) == 3
    assert next(e for e in es if e['term'] == 'CNN')['state'] == '否定使用'
    assert not any(e['state'] == '使用线索' for e in es if e['term'] == 'ResNet')


@pytest.mark.parametrize('text,expected', [
    ('We use BERT and do not use CNN.', ['使用线索', '否定使用']),
    ('We use BERT and mention CNN.', ['使用线索', '仅提及或待核对']),
    ('We use BERT, while prior work uses CNN.', ['使用线索', '仅提及或待核对']),
    ('We use BERT not CNN.', ['使用线索', '否定使用']),
])
def test_usage_is_scoped_to_entity_clause(tmp_path, text, expected):
    f = tmp_path / 'scope.txt'
    f.write_text(text, encoding='utf-8')
    p = ResearchProject()
    p.import_files([f])
    states = {e['term']: e['state'] for e in p.evidence()}
    assert [states['BERT'], states['CNN']] == expected


def test_export_enforces_import_uncompressed_limit(tmp_path, monkeypatch):
    import doclens.research as research
    p = ResearchProject()
    p.import_files(corpus(tmp_path))
    monkeypatch.setattr(research, 'LIMIT', len(p._data()) + 50)
    target = tmp_path / 'too-large.zip'
    with pytest.raises(ValueError, match='上限'):
        p.export_bundle(target)
    assert not target.exists()


def test_reimport_recovers_missing_originals(tmp_path):
    p = ResearchProject()
    paths = corpus(tmp_path)
    p.import_files(paths)
    bundle = tmp_path / 'without.zip'
    p.export_bundle(bundle)
    shared = ResearchProject.load(bundle)
    shared.import_files(paths)
    shared.export_bundle(tmp_path / 'with.zip', True)
    assert len(shared.documents) == len(paths) == len(shared.originals)


@pytest.mark.parametrize('body', ['We use BERT. ' * 1500, 'BERT ' * 1500])
def test_long_paragraph_classification_scans_each_clause_once(tmp_path, monkeypatch, body):
    import doclens.research as research
    f = tmp_path / 'long.txt'
    f.write_text(body, encoding='utf-8')
    p = ResearchProject()
    p.import_files([f])
    original = research._state
    scanned = []
    def count(text, *args):
        scanned.append(len(text))
        return original(text, *args)
    monkeypatch.setattr(research, '_state', count)
    assert len(p.evidence()) == 1500
    assert max(scanned) <= 350


def test_multiword_entity_anchors_are_valid_markdown_urls(tmp_path):
    f = tmp_path / 'random.txt'
    f.write_text('We use Random Forest.', encoding='utf-8')
    p = ResearchProject()
    p.import_files([f])
    e = p.evidence()[0]
    p.save_note('', 'Check method', e['id'])
    assert ' ' not in e['id']
    assert f"(#e-{e['id']})" in p.markdown()
