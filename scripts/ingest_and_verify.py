import uuid
import requests
import json
import time
from pathlib import Path

BASE = "http://127.0.0.1:8000"
USERNAME = "uploader_" + uuid.uuid4().hex[:8]
PASSWORD = "SecretPass123"
FILEPATH = Path("README.md")

print('Using file:', FILEPATH.resolve())

# Register
r = requests.post(f"{BASE}/auth/register", json={"username": USERNAME, "password": PASSWORD})
print('\nREGISTER status:', r.status_code)
print(r.text)

# Login
r2 = requests.post(f"{BASE}/auth/login", data={"username": USERNAME, "password": PASSWORD})
print('\nLOGIN status:', r2.status_code)
print(r2.text)
if r2.status_code != 200:
    raise SystemExit('Login failed')

token = r2.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Upload
with open(FILEPATH, 'rb') as f:
    files = {'file': (FILEPATH.name, f, 'text/markdown')}
    r3 = requests.post(f"{BASE}/documents/upload", headers=headers, files=files)
print('\nUPLOAD status:', r3.status_code)
print(r3.text)

# Wait a moment for Qdrant write to surface
time.sleep(1)

# Query Qdrant collection info
import urllib.request
info = json.load(urllib.request.urlopen('http://localhost:6333/collections/study_notes'))
print('\nQDRANT collection info:')
print(json.dumps(info, indent=2))

# List documents via API
r4 = requests.get(f"{BASE}/documents", headers=headers)
print('\nGET /documents status:', r4.status_code)
print(r4.text)

# Run MCP search test script
import subprocess
print('\nRunning test_mcp_http.py')
proc = subprocess.run(["python", "test_mcp_http.py"], capture_output=True, text=True)
print('RETURN CODE:', proc.returncode)
print('STDOUT:\n', proc.stdout)
print('STDERR:\n', proc.stderr)

# Call MCP list_sources and get_document via FastMCP client
try:
    from fastmcp import Client
    import asyncio

    async def call_tools():
        async with Client('http://127.0.0.1:8000/mcp/') as client:
            ls = await client.call_tool('list_sources', {'user_id': r3.json().get('user_id') or r2.json().get('access_token')})
            print('\nMCP list_sources result:')
            print(ls)
            # pick first doc id
            if ls and ls.get('results'):
                doc_id = ls['results'][0]['doc_id']
                gd = await client.call_tool('get_document', {'doc_id': doc_id, 'user_id': ls['results'][0].get('user_id') or r3.json().get('user_id')})
                print('\nMCP get_document result:')
                print(gd)

    asyncio.run(call_tools())
except Exception as e:
    print('\nMCP client calls failed:', e)
