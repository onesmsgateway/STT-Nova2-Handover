import os
import logging
from typing import List, Optional
logger = logging.getLogger(__name__)
USE_LOCAL_EMBEDDINGS_FALLBACK = os.getenv('USE_LOCAL_EMBEDDINGS_FALLBACK', 'true').lower() == 'true'
LOCAL_EMBEDDING_MODEL = os.getenv('LOCAL_EMBEDDING_MODEL', 'all-mpnet-base-v2')

class LocalEmbeddingClient:

    def __init__(self, model_name: str=None):
        self.model_name = model_name or LOCAL_EMBEDDING_MODEL
        self._model = None
        self._initialized = False
        self._init_error = None

    def _ensure_model(self):
        if self._initialized:
            return self._model is not None
        self._initialized = True
        if not USE_LOCAL_EMBEDDINGS_FALLBACK:
            logger.info('🔇 Local embeddings fallback is disabled')
            return False
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f'📦 Loading local embedding model: {self.model_name}...')
            self._model = SentenceTransformer(self.model_name)
            test_embedding = self._model.encode('test', convert_to_numpy=True)
            self._dimension = len(test_embedding)
            logger.info(f'✅ Local embedding model loaded successfully ({self._dimension} dimensions)')
            return True
        except ImportError:
            self._init_error = 'sentence-transformers not installed'
            logger.error('❌ sentence-transformers not installed. Run: pip install sentence-transformers')
            return False
        except Exception as e:
            self._init_error = str(e)
            logger.error(f'❌ Failed to load local embedding model: {e}')
            return False

    @property
    def is_available(self) -> bool:
        return self._ensure_model()

    @property
    def dimension(self) -> int:
        if self._model is not None:
            return self._dimension
        return 768

    def get_embedding(self, text: str) -> List[float]:
        if not self._ensure_model():
            raise RuntimeError(f'Local embedding model not available: {self._init_error}')
        try:
            text = text.replace('\n', ' ').strip()
            if not text:
                raise ValueError('Empty text cannot be embedded')
            embedding = self._model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f'❌ Local embedding error: {e}')
            raise

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        if not self._ensure_model():
            raise RuntimeError(f'Local embedding model not available: {self._init_error}')
        try:
            cleaned_texts = [t.replace('\n', ' ').strip() for t in texts if t.strip()]
            if not cleaned_texts:
                return []
            embeddings = self._model.encode(cleaned_texts, convert_to_numpy=True)
            return [emb.tolist() for emb in embeddings]
        except Exception as e:
            logger.error(f'❌ Batch embedding error: {e}')
            raise
local_embedding_client = LocalEmbeddingClient()