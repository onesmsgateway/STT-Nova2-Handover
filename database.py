import asyncio
import logging
from typing import Optional, Dict, Any
from sqlalchemy import create_engine, text, MetaData, Table, Column, String, Text, DateTime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import config
logger = logging.getLogger(__name__)

class DatabaseManager:

    def __init__(self):
        self.engine = None
        self.async_engine = None
        self.session_factory = None
        self.async_session_factory = None
        self.is_connected = False

    async def initialize(self):
        if not config.POSTGRESQL_ENABLED:
            logger.info('PostgreSQL disabled in config')
            return
        try:
            self.engine = create_engine(config.POSTGRESQL_CONNECTION_STRING, pool_size=config.POSTGRESQL_POOL_SIZE, max_overflow=config.POSTGRESQL_MAX_OVERFLOW, pool_timeout=config.POSTGRESQL_POOL_TIMEOUT, pool_recycle=config.POSTGRESQL_POOL_RECYCLE, echo=False, connect_args={'sslmode': 'disable'})
            async_connection_string = config.POSTGRESQL_CONNECTION_STRING.replace('postgresql://', 'postgresql+asyncpg://')
            self.async_engine = create_async_engine(async_connection_string, pool_size=config.POSTGRESQL_POOL_SIZE, max_overflow=config.POSTGRESQL_MAX_OVERFLOW, pool_timeout=config.POSTGRESQL_POOL_TIMEOUT, pool_recycle=config.POSTGRESQL_POOL_RECYCLE, echo=False, connect_args={'ssl': 'disable'})
            self.session_factory = sessionmaker(bind=self.engine)
            self.async_session_factory = sessionmaker(bind=self.async_engine, class_=AsyncSession, expire_on_commit=False)
            await self.test_connection()
            self.is_connected = True
            logger.info('PostgreSQL connection initialized successfully')
        except Exception as e:
            logger.error(f'Failed to initialize PostgreSQL connection: {e}')
            self.is_connected = False
            raise

    async def test_connection(self):
        try:
            async with self.async_engine.begin() as conn:
                result = await conn.execute(text('SELECT 1'))
                result.fetchone()
            logger.info('PostgreSQL connection test successful')
        except Exception as e:
            logger.error(f'PostgreSQL connection test failed: {e}')
            raise

    async def update_cdr_transcript(self, cdr_uuid: str, transcript: str, summary: str, call_topic: str='N/A') -> bool:
        if not self.is_connected or not config.POSTGRESQL_ENABLED:
            logger.warning('PostgreSQL not connected or disabled')
            return False
        if not cdr_uuid:
            logger.warning('cdr_uuid is empty, skipping database update')
            return False
        try:
            async with self.async_session_factory() as session:
                update_query = text(f'\n                    UPDATE {config.POSTGRESQL_TABLE_CDR} \n                    SET transcript = :transcript,\n                        summary = :summary,\n                        call_topic = :call_topic\n                    WHERE cdr_uuid = :cdr_uuid\n                ')
                result = await session.execute(update_query, {'transcript': transcript, 'summary': summary, 'call_topic': call_topic, 'cdr_uuid': cdr_uuid})
                await session.commit()
                if result.rowcount > 0:
                    logger.info(f'Successfully updated CDR record: {cdr_uuid}')
                    return True
                else:
                    logger.warning(f'No CDR record found with uuid: {cdr_uuid}')
                    return False
        except SQLAlchemyError as e:
            logger.error(f'Database error updating CDR record {cdr_uuid}: {e}')
            return False
        except Exception as e:
            logger.error(f'Unexpected error updating CDR record {cdr_uuid}: {e}')
            return False

    async def close(self):
        try:
            if self.async_engine:
                await self.async_engine.dispose()
            if self.engine:
                self.engine.dispose()
            self.is_connected = False
            logger.info('PostgreSQL connections closed')
        except Exception as e:
            logger.error(f'Error closing PostgreSQL connections: {e}')
db_manager = DatabaseManager()