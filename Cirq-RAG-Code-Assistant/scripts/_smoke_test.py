"""
Smoke test — verifies config.dev.json is loaded and Ollama is reachable.
Run from the Cirq-RAG-Code-Assistant directory:
  conda run -n cnn python scripts/_smoke_test.py
"""
import os, sys
sys.path.insert(0, '.')

# config_loader auto-picks config.dev.json when ENVIRONMENT=development (default)
from src.cirq_rag_code_assistant.config import get_config
cfg = get_config()

print('Config loaded OK')
print('  Environment       :', cfg.get('app', {}).get('environment', '?'))
print('  Embedding provider:', cfg['models']['embedding']['provider'])
print('  Embedding model   :', cfg['models']['embedding']['model_name'])
print('  Embedding device  :', cfg['models']['embedding']['device'])
print('  Designer model    :', cfg['agents']['designer']['model']['model'])
print('  Designer provider :', cfg['agents']['designer']['model']['provider'])

assert cfg['models']['embedding']['provider'] == 'local', \
    'FAIL: still loading AWS config - check config/config.dev.json exists'
assert cfg['agents']['designer']['model']['provider'] == 'ollama', \
    'FAIL: designer not set to ollama'

import requests
try:
    r = requests.get('http://localhost:11434/api/tags', timeout=5)
    models = [m['name'] for m in r.json().get('models', [])]
    target = 'qwen2.5-coder:7b-instruct-q4_K_M'
    found = any(target in m for m in models)
    print('  Ollama reachable  : YES  ({} models)'.format(len(models)))
    print('  Target model      :', 'FOUND' if found else 'NOT FOUND - run: ollama pull ' + target)
    if found:
        print('\n  Testing Ollama generation...')
        payload = {
            "model": target,
            "prompt": "Write: import cirq",
            "stream": False,
            "options": {"num_predict": 8}
        }
        rg = requests.post('http://localhost:11434/api/generate', json=payload, timeout=60)
        rg.raise_for_status()
        reply = rg.json().get('response', '')[:80]
        print('  Response snippet  :', repr(reply))
        print('\n  [ALL CHECKS PASSED] Ready to benchmark.')
except Exception as e:
    print('  Ollama reachable  : NO  ({})'.format(e))
