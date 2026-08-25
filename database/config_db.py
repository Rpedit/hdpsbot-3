import libsql_client
from info import LIBSQL_URL, LIBSQL_AUTH_TOKEN
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

class Database:
    def __init__(self, url, db_name):
        self.url = LIBSQL_URL
        self.auth_token = LIBSQL_AUTH_TOKEN
        self._client = None

    async def get_client(self):
        if self._client is None:
            self._client = libsql_client.create_client(url=self.url, auth_token=self.auth_token)
            await self._create_tables()
        return self._client

    async def _create_tables(self):
        try:
            client = await self.get_client()
            await client.execute("""
                CREATE TABLE IF NOT EXISTS user_messages (
                    user_id INTEGER,
                    text TEXT,
                    count INTEGER DEFAULT 1,
                    PRIMARY KEY (user_id, text)
                )
            """)
        except Exception as e:
            logger.error(f"Table creation error in user_messages: {e}")

    async def update_top_messages(self, user_id, message_text):
        try:
            client = await self.get_client()
            await client.execute("""
                INSERT INTO user_messages (user_id, text, count) 
                VALUES (?, ?, 1)
                ON CONFLICT(user_id, text) DO UPDATE SET count = count + 1
            """, (int(user_id), message_text))
        except Exception as e:
            logger.error(f"Error updating top messages: {e}")

    async def get_top_messages(self, limit=30):
        try:
            client = await self.get_client()
            res = await client.execute("""
                SELECT text FROM user_messages 
                GROUP BY text 
                ORDER BY SUM(count) DESC 
                LIMIT ?
            """, (int(limit),))
            rows = getattr(res, 'rows', None) or []
            return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"Error getting top messages: {e}")
            return []
    
    async def delete_all_messages(self):
        try:
            client = await self.get_client()
            await client.execute("DELETE FROM user_messages")
            print("All filenames notification / messages have been deleted.")
            return True
        except Exception as e:
            logger.error(f"Error deleting messages: {e}")
            return False

mdb = Database(LIBSQL_URL, "admin_database")
