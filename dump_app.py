import sys
with open('src/App.tsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()
mid = len(lines) // 2
cut = mid
for i in range(mid, min(mid + 20, len(lines))):
    if lines[i].strip() == '' or lines[i].strip().startswith('//'):
        cut = i + 1
        break
with open('..\\_dump\\App_part1.txt', 'w', encoding='utf-8') as f:
    f.writelines(lines[:cut])
with open('..\\_dump\\App_part2.txt', 'w', encoding='utf-8') as f:
    f.writelines(lines[cut:])
print(f'Разрезано: part1={cut} строк, part2={len(lines)-cut} строк')
print(f'Общий размер: {sum(len(l.encode("utf-8")) for l in lines)} байт')