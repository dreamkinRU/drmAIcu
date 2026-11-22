import ast
import json
import os
import sys
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, 'diag_ollama.txt')
buf = []


def p(*args):
    s = ' '.join(str(a) for a in args)
    print(s)
    buf.append(s)


def http_get(url, timeout=3):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read().decode('utf-8', 'replace')
    except Exception as e:
        return None, str(e)


def dump_funcs(path, wanted_names=None, decorator_filter=None, max_lines=100):
    if not os.path.exists(path):
        p('  ФАЙЛ НЕ НАЙДЕН:', path)
        return
    src = open(path, encoding='utf-8').read()
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        p('  SYNTAX ERROR:', e)
        return

    def decorators(node):
        return ' '.join(ast.get_source_segment(src, d) or '' for d in node.decorator_list)

    def dump(node, prefix=''):
        seg = ast.get_source_segment(src, node) or ''
        lines = seg.split('\n')
        p('  ' + prefix + '--- ' + node.name + ' (строка ' + str(node.lineno) + ') ---')
        for ln in lines[:max_lines]:
            p('  ' + prefix + ln)
        if len(lines) > max_lines:
            p('  ' + prefix + '... [обрезано, всего ' + str(len(lines)) + ' строк]')
        p('')

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if decorator_filter and decorator_filter in decorators(node):
            dump(node)
        elif wanted_names and node.name in wanted_names:
            dump(node)


p('=' * 70)
p('ДИАГНОСТИКА OLLAMA')
p('=' * 70)
p('Python:', sys.version.split()[0])
p('BASE:', BASE)
p('')

p('--- Пакет ollama ---')
try:
    import ollama
    p('  установлен, версия:', getattr(ollama, '__version__', 'неизвестна'))
    p('  путь:', getattr(ollama, '__file__', '?'))
except ImportError as e:
    p('  НЕ установлен:', e)
p('')

p('--- Прямой доступ к Ollama API ---')
for host in ('http://127.0.0.1:11434', 'http://localhost:11434'):
    status, body = http_get(host + '/api/tags')
    p('  GET ' + host + '/api/tags ->', status)
    if status == 200:
        try:
            data = json.loads(body)
            models = data.get('models', [])
            p('  моделей:', len(models))
            for m in models:
                size_gb = round(m.get('size', 0) / 1024 / 1024 / 1024, 2)
                p('    -', m.get('name'), '|', size_gb, 'GB')
        except Exception as e:
            p('  ошибка разбора:', e)
    else:
        p('  ', body[:200])
p('')

p('--- Загруженные в память модели (/api/ps) ---')
status, body = http_get('http://127.0.0.1:11434/api/ps')
p('  status:', status)
p('  ', body[:500])
p('')

p('--- Эндпоинты бэкенда (порт 8080) ---')
for ep in ('/api/status', '/api/ollama/models'):
    status, body = http_get('http://127.0.0.1:8080' + ep)
    p('  GET ' + ep, '->', status)
    p('  ', body[:400])
p('')

p('=' * 70)
p('main.py: эндпоинты ollama и task')
p('=' * 70)
dump_funcs(os.path.join(BASE, 'main.py'), decorator_filter='ollama')
dump_funcs(os.path.join(BASE, 'main.py'), decorator_filter='/api/task')

p('=' * 70)
p('agent_engine.py: run_task, _query_ollama, __init__')
p('=' * 70)
dump_funcs(
    os.path.join(BASE, 'agent_engine.py'),
    wanted_names={'run_task', '_query_ollama', '__init__', 'get_engine'},
)

p('=' * 70)
p('agent_engine.py: строки с ollama / host / Client / model')
p('=' * 70)
ae = os.path.join(BASE, 'agent_engine.py')
if os.path.exists(ae):
    for i, line in enumerate(open(ae, encoding='utf-8'), 1):
        low = line.lower()
        if any(k in low for k in ('ollama', '11434', 'client(', 'default_model', 'num_predict')):
            p('  ' + str(i).rjust(4) + ': ' + line.rstrip())
p('')

open(OUT, 'w', encoding='utf-8').write('\n'.join(buf))
print('\n>>> Результат сохранён в', OUT)