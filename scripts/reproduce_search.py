import sys
import os
import traceback

# Ensure project root is on sys.path so 'backend' package imports work
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from backend.retrieval.retrieval_service import RetrievalService
from backend.app.core.config import get_settings
from backend.app.core.config import Settings

settings = get_settings()
print('Embedding provider:', settings.embedding_provider)
print('OpenAI key configured:', bool(settings.openai_api_key.strip()))
print('Qdrant URL:', settings.qdrant_url)

try:
    RetrievalService().search('CPU Scheduling', 'user-123', 5)
except Exception as e:
    traceback.print_exc()
    print('TYPE:', type(e))
    print('STR :', str(e))
    print('REPR:', repr(e))


print('\n--- Reproduce OpenAI provider failure (missing API key) ---')
try:
    s = Settings(embedding_provider='openai', openai_api_key='')
    RetrievalService(settings=s).search('CPU Scheduling', 'user-123', 5)
except Exception as e:
    traceback.print_exc()
    print('TYPE:', type(e))
    print('STR :', str(e))
    print('REPR:', repr(e))


print('\n--- Reproduce Qdrant connection failure (bad URL) ---')
try:
    s2 = Settings(embedding_provider='local', local_embedding_model=settings.local_embedding_model, qdrant_url='http://nonexistent:6333')
    RetrievalService(settings=s2).search('CPU Scheduling', 'user-123', 5)
except Exception as e:
    traceback.print_exc()
    print('TYPE:', type(e))
    print('STR :', str(e))
    print('REPR:', repr(e))
