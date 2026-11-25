#!/usr/bin/env python3
import json, urllib.request, urllib.parse, time, os

# Load the data.json to get model IDs
with open('data.json') as f:
    rows = json.load(f)

# Get API key
key = os.environ.get('OPENROUTER_API_KEY', '').strip()
if not key:
    with open(os.path.expanduser('~/.hermes/.env')) as f:
        for line in f:
            if line.startswith('OPENROUTER_API_KEY='):
                key = line.split('=', 1)[1].strip().strip('"\'')
                break

if not key:
    print('No API key found')
    exit(1)

UA = {'User-Agent': 'Hermes-Agent/1.0'}
flex = {}
oids = {r['id'] for r in rows}
print(f'Checking {len(oids)} models...')

for i, oid in enumerate(sorted(oids)):
    try:
        url = f'https://openrouter.ai/api/v1/models/{urllib.parse.quote(oid)}/endpoints'
        req = urllib.request.Request(url, headers={'Authorization': f'Bearer {key}', **UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
        
        best_flex = None
        for ep in data.get('data', {}).get('endpoints', []):
            if ep.get('service_tier') == 'flex':
                p = ep.get('pricing', {})
                in_p = float(p.get('prompt', 0)) * 1e6
                out_p = float(p.get('completion', 0)) * 1e6
                cache_p = float(p.get('input_cache_read', 0)) * 1e6
                if best_flex is None or in_p < best_flex['in']:
                    best_flex = {'in': in_p, 'out': out_p, 'cache': cache_p, 'provider': ep['provider_name']}
        
        if best_flex:
            flex[oid] = best_flex
            print(f'  OK {oid}: in={best_flex["in"]}, out={best_flex["out"]}, cache={best_flex["cache"]} ({best_flex["provider"]})')
        else:
            print(f'  -- {oid}: no flex')
    except Exception as e:
        print(f'  ERR {oid}: {e}')
    
    if i % 10 == 9:
        time.sleep(1)
    else:
        time.sleep(0.3)

with open('data/flex_pricing.json', 'w') as f:
    json.dump(flex, f, ensure_ascii=False)
print(f'\nDone: {len(flex)}/{len(oids)} models with Flex')