# -*- coding: utf-8 -*-
"""B69: гигиена Markdown-документации.

Панель drmAIcu рендерит MD через react-markdown + remark-breaks: одиночный
перенос строки превращается в <br>. Поэтому жёсткие переносы внутри абзацев
(«простыня посреди предложения») запрещены: каждый абзац — одна строка.
Бэкслэш-экранирование и вложенные списки — разрешены.
"""
import io
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LIST_RE = re.compile(r'^\s*([-*+]|\d+[.)])\s')


def _wrapped_paragraph_lines(text):
    """Строки-продолжения абзацев вне код-блоков (нежелательные)."""
    lines = text.split('\n')
    infence = False
    bad = []
    for i, ln in enumerate(lines, 1):
        s = ln.strip()
        if s.startswith('```') or s.startswith('~~~'):
            infence = not infence
            continue
        if infence:
            continue
        if ln.startswith((' ', '\t')) and s and not LIST_RE.match(ln):
            bad.append((i, s))
    return bad


@pytest.mark.parametrize('path', [
    'README.md',
    'docs/ARCHITECTURE.md',
    'docs/USER_GUIDE.md',
    'docs/NEW_FEATURES.md',
    'docs/PLUGIN_SYSTEM.md',
    'docs/PLUGIN_API_CONTRACT.md',
    'docs/CHANGELOG.md',
])
def test_docs_have_no_hard_wrapped_paragraphs(path):
    text = io.open(ROOT / path, encoding='utf-8', newline='').read()
    bad = _wrapped_paragraph_lines(text)
    assert not bad, (
        'жёсткие переносы внутри абзацев ломают рендер в панели '
        f'({path}, строки {[n for n, _ in bad]}): JOIN CONTINUATION LINES'
    )


def test_changelog_is_crlf():
    raw = io.open(ROOT / 'docs' / 'CHANGELOG.md', encoding='utf-8', newline='').read()
    assert '\r\n' in raw and raw.count('\r\n') >= raw.count('\n') - 1, (
        'docs/CHANGELOG.md должен сохранять CRLF; путь исправления: писать с newline=""'
    )


def test_mdtab_renders_explicit_github_like_headings():
    src = io.open(ROOT / 'src' / 'components' / 'tabs' / 'MDTab.tsx', encoding='utf-8', newline='').read()
    assert 'mdComponents' in src, 'MDTab должен задавать явные стили заголовков (mdComponents)'
    for token in ('h1:', 'h2:', 'border-b'):
        assert token in src, f'в MDTab.tsx нет {token}; путь исправления: вернуть components-переопределения заголовков'
