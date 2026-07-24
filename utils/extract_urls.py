import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with open(os.path.join(BASE, 'postman', 'Quirk_Translator_IBM_AWS.postman_collection_original.json'), encoding='utf-8') as f:
    data = json.load(f)

results = []

for group in data['item']:
    for sub in group['item']:
        raw = sub['request']['body']['raw']
        body = json.loads(raw)
        endpoint = sub['request']['url']['raw']
        prefix = f"{group['name']} / {sub['name']}"
        n = 0
        for k, v in body.items():
            if isinstance(v, str) and 'algassert.com' in v:
                circuit = v.split('circuit=')[1]
                url = f"https://algassert.com/quirk#circuit={circuit}"
                name = f"{prefix} [{k}]" if len([x for x in body.values() if isinstance(x, str) and 'algassert.com' in x]) > 1 else prefix
                results.append((name, endpoint, url))
                n += 1

with open(os.path.join(BASE, 'quirks_urls.txt'), 'w', encoding='utf-8') as f:
    for i, (name, endpoint, url) in enumerate(results, 1):
        f.write(f"{i:2d}. {name}\n")
        f.write(f"    POST {endpoint}\n")
        f.write(f"    {url}\n\n")

print(f"Total: {len(results)} entradas")
