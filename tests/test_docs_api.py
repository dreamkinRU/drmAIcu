# -*- coding: utf-8 -*-
"""Тесты /api/md-маршрута документации (v.3.10.0: вся документация в docs/).

Проверяют is_doc_rel (только *.md в корне и docs/), safe_path (защита от
обхода каталога) и фактическое чтение реальных доков через TestClient.
"""
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import guards
import patch_engine as engine
import main

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_is_doc_rel_allows_root_and_docs_md():
    assert guards.is_doc_rel('README.md') is True
    assert guards.is_doc_rel('docs/PLUGIN_SYSTEM.md') is True
    assert guards.is_doc_rel('docs/ARCHITECTURE.md') is True


def test_is_doc_rel_rejects_non_md_and_traversal():
    assert guards.is_doc_rel('main.py') is False
    # любая глубина под docs/ разрешена (безопасность обеспечивает safe_path)
    assert guards.is_doc_rel('docs/sub/X.md') is True
    assert guards.is_doc_rel('docs/../main.py') is False
    assert guards.is_doc_rel('..\\x.md') is False
    assert guards.is_doc_rel('') is False
    assert guards.is_doc_rel('docs//X.md') is False


def test_md_get_real_docs_files():
    client = TestClient(main.app)
    for doc in ('docs/PLUGIN_SYSTEM.md', 'docs/PLUGIN_API_CONTRACT.md',
                'docs/ARCHITECTURE.md', 'docs/CHANGELOG.md', 'README.md'):
        r = client.get('/api/md/' + doc)
        assert r.status_code == 200, doc
        data = r.json()
        assert data.get('error') in (None, ''), doc
        assert len(data.get('content', '')) > 100, doc + ' пуст'


def test_md_get_docs_in_tmp_base(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, 'BASE', str(tmp_path))
    (tmp_path / 'docs').mkdir()
    (tmp_path / 'docs' / 'IDX.md').write_text('# \u0438\u043d\u0434\u0435\u043a\u0441 docs', encoding='utf-8')
    client = TestClient(main.app)
    r = client.get('/api/md/docs/IDX.md')
    assert r.status_code == 200
    assert r.json()['content'] == '# \u0438\u043d\u0434\u0435\u043a\u0441 docs'


def test_md_get_rejects_non_docs_subdir(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, 'BASE', str(tmp_path))
    (tmp_path / 'sub').mkdir()
    (tmp_path / 'sub' / 'X.md').write_text('secret', encoding='utf-8')
    client = TestClient(main.app)
    # a/b.md (не docs/) запрещён is_doc_rel
    r = client.get('/api/md/sub/X.md')
    assert r.status_code == 200
    assert 'error' in r.json() and r.json()['content'] == ''
    # обход каталога через docs/.. блокируется
    r2 = client.get('/api/md/docs/../X.md')
    assert 'error' in r2.json()


def test_md_get_not_found_error_is_plain_text():
    client = TestClient(main.app)
    r = client.get('/api/md/docs/NOPE.md')
    assert r.status_code == 200
    data = r.json()
    assert data['content'] == '' and data['error'] == 'not found'
