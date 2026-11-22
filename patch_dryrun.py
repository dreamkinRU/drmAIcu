import json, sys, os

def check(patch_file):
    with open(patch_file, 'r', encoding='utf-8') as f:
        patch = json.load(f)
    print(f"=== ДРАЙ-РУН {patch_file} ===")
    ok = True
    for i, op in enumerate(patch['operations'], 1):
        tgt = op['target_file']
        if not os.path.exists(tgt):
            print(f"  Op {i}: ФАЙЛ НЕ НАЙДЕН {tgt}"); ok = False; continue
        content = open(tgt, encoding='utf-8').read()
        find = op.get('find', '')
        if find in content:
            cnt = content.count(find)
            print(f"  Op {i}: ✅ НАЙДЕНО ({cnt}x) в {tgt}")
            if cnt > 1:
                print(f"          ⚠️ AMBIGUOUS — движок отклонит!"); ok = False
        else:
            print(f"  Op {i}: ❌ НЕ НАЙДЕНО в {tgt}")
            print(f"          find = {repr(find[:120])}")
            # подсказка: показать ближайшую реальную строку
            for line in content.splitlines():
                if find[:30].strip() and find[:30].strip() in line:
                    print(f"          близко: {repr(line)}"); break
            ok = False
    print("=== ИТОГ:", "ПРИМЕНИМ" if ok else "БУДЕТ ОТКЛОНЁН", "===")
    return ok

if __name__ == '__main__':
    check(sys.argv[1] if len(sys.argv) > 1 else 'patch/next.json')