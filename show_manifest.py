# show_manifest.py
with open('main.py', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'save_manifest(man)' in line:
        start = max(0, i - 5)
        end = min(len(lines), i + 5)
        print(f'--- Context around line {i+1} ---')
        for j in range(start, end):
            marker = '>>>' if j == i else '   '
            print(f'{marker} {j+1:4}: {lines[j]}', end='')
        print('\n')