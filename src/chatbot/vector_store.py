import logging
import psycopg2
from pgvector.psycopg2 import register_vector
import psycopg2.extras
import config
from .llm_client import gemini_client
from typing import List, Dict, Any, Optional
logger = logging.getLogger(__name__)

class VectorStore:

    def __init__(self):
        self.conn = None
        self.connect()

    def connect(self):
        try:
            if self.conn and (not self.conn.closed):
                try:
                    self.conn.close()
                except:
                    pass
            self.conn = psycopg2.connect(host=config.VECTOR_DB_HOST, port=config.VECTOR_DB_PORT, user=config.VECTOR_DB_USER, password=config.VECTOR_DB_PASSWORD, dbname=config.VECTOR_DB_NAME, connect_timeout=5)
            logger.info('✅ Connected to Vector DB successfully')
            try:
                register_vector(self.conn)
            except Exception as e:
                logger.error(f'Failed to register vector adapter: {e}')
            self.create_flags_table_if_not_exists()
        except Exception as e:
            logger.error(f'❌ Failed to connect to Vector DB: {e}')
            self.conn = None

    def ensure_connection(self):
        if self.conn is None:
            logger.warning('Connection is None, reconnecting...')
            self.connect()
            return
        try:
            if self.conn.closed:
                logger.warning('Connection is closed, reconnecting...')
                self.connect()
                return
            with self.conn.cursor() as cur:
                cur.execute('SELECT 1')
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f'Connection dead ({e}), reconnecting...')
            self.connect()
        except Exception as e:
            logger.error(f'Unexpected connection error: {e}')
            self.connect()

    def get_tenant_schema(self, school_code: str) -> str:
        self.ensure_connection()
        if not self.conn:
            return None
        try:
            cur = self.conn.cursor()
            cur.execute('SELECT schema_name FROM public.tenants WHERE school_code = %s', (school_code,))
            row = cur.fetchone()
            cur.close()
            if row:
                return row[0]
            logger.warning(f'Tenant schema not found for school_code: {school_code}')
            return None
        except Exception as e:
            logger.error(f'Failed to resolve tenant schema: {e}')
            return None

    async def add_document(self, text: str, filename: str, metadata: Dict=None) -> bool:
        logger.warning('add_document called on Stateless Vector Store. Ignored or Deprecated.')
        return False

    async def search(self, query: str, school_code: str, limit: int=3) -> List[Dict[str, Any]]:
        self.ensure_connection()
        if not self.conn:
            logger.error('Cannot search: Database connection failed')
            return []
        if not school_code:
            logger.error('Search failed: school_code is required')
            return []
        schema = self.get_tenant_schema(school_code)
        if not schema:
            return []
        try:
            query_embedding = await gemini_client.get_embedding(query)
            cur = self.conn.cursor()
            sql = f'\n                SELECT \n                    rv.content_chunk, \n                    r.filename, \n                    rv.metadata, \n                    1 - (rv.embedding <=> %s::vector) as similarity\n                FROM {schema}.resource_vectors rv\n                JOIN {schema}.resources r ON rv.resource_id = r.id\n                ORDER BY similarity DESC\n                LIMIT %s\n            '
            cur.execute(sql, (query_embedding, limit))
            rows = cur.fetchall()
            results = []
            for row in rows:
                results.append({'content': row[0], 'filename': row[1], 'metadata': row[2], 'similarity': row[3]})
            cur.close()
            return results
        except Exception as e:
            logger.error(f'❌ Search failed: {e}')
            try:
                self.conn.rollback()
            except:
                pass
            return []

    async def save_vectors(self, resource_id: str, chunks: List[str], metadata: Dict, school_code: str):
        self.ensure_connection()
        if not self.conn:
            raise Exception('Database connection failed')
        schema = self.get_tenant_schema(school_code)
        if not schema:
            raise Exception(f'Schema not found for school_code {school_code}')
        try:
            cur = self.conn.cursor()
            embeddings = []
            for chunk in chunks:
                emb = await gemini_client.get_embedding(chunk)
                embeddings.append(emb)
            sql = f'\n                INSERT INTO {schema}.resource_vectors (resource_id, content_chunk, embedding, metadata)\n                VALUES (%s, %s, %s::vector, %s)\n            '
            for i, chunk in enumerate(chunks):
                cur.execute(sql, (resource_id, chunk, embeddings[i], psycopg2.extras.Json(metadata)))
            self.conn.commit()
            cur.close()
            logger.info(f'✅ Saved {len(chunks)} vectors for resource {resource_id}')
            return True
        except Exception as e:
            logger.error(f'❌ Save vectors failed: {e}')
            try:
                self.conn.rollback()
            except:
                pass
            raise e

    def create_flags_table_if_not_exists(self):
        if not self.conn:
            return
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.flagged_content');")
                if cur.fetchone()[0] is None:
                    cur.execute('\n                        CREATE TABLE public.flagged_content (\n                            id SERIAL PRIMARY KEY,\n                            service_name VARCHAR(255),\n                            ip_address VARCHAR(255),\n                            user_identifier VARCHAR(255),\n                            content TEXT,\n                            flagged_category VARCHAR(255),\n                            reason TEXT,\n                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n                        );\n                    ')
                    self.conn.commit()
                    logger.info("✅ Created 'flagged_content' table")
                else:
                    logger.info("✅ Verified 'flagged_content' table exists")
        except Exception as e:
            logger.error(f'❌ Failed to create flagged_content table: {e}')
            self.conn.rollback()

    def log_flagged_content(self, service_name: str, ip_address: str, user_identifier: str, content: str, category: str, reason: str):
        self.ensure_connection()
        if not self.conn:
            return False
        try:
            with self.conn.cursor() as cur:
                cur.execute('\n                    INSERT INTO public.flagged_content \n                    (service_name, ip_address, user_identifier, content, flagged_category, reason)\n                    VALUES (%s, %s, %s, %s, %s, %s)\n                ', (service_name, ip_address, user_identifier, content, category, reason))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f'❌ Failed to log flagged content: {e}')
            return False

    def get_flagged_content(self, limit: int=100):
        self.ensure_connection()
        if not self.conn:
            return []
        try:
            with self.conn.cursor() as cur:
                cur.execute('\n                    SELECT id, service_name, ip_address, user_identifier, content, flagged_category, reason, created_at\n                    FROM public.flagged_content\n                    ORDER BY created_at DESC\n                    LIMIT %s\n                ', (limit,))
                rows = cur.fetchall()
            results = []
            columns = ['id', 'service_name', 'ip_address', 'user_identifier', 'content', 'flagged_category', 'reason', 'created_at']
            for row in rows:
                results.append(dict(zip(columns, row)))
            return results
        except Exception as e:
            logger.error(f'❌ Failed to get flagged content: {e}')
            return []

    def delete_flagged_content(self, msg_id: int):
        self.ensure_connection()
        if not self.conn:
            return False
        try:
            with self.conn.cursor() as cur:
                cur.execute('DELETE FROM public.flagged_content WHERE id = %s', (msg_id,))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f'❌ Failed to delete flagged content: {e}')
            return False
vector_store = VectorStore()