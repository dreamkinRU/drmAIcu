import json, sys, importlib

main = importlib.import_module('main')
res = main.apply_patch(json.load(open(sys.argv[1], encoding='utf-8')))
print('SUCCESS' if res.get('success') else 'FAILED')
print(res.get('message') or res.get('error'))
sys.exit(0 if res.get('success') else 1)