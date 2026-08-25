import libsql_client
from info import LIBSQL_URL, LIBSQL_AUTH_TOKEN
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

class UserTracker:
    def __init__(self, url, auth_token):
        self.url = url
        self.auth_token = auth_token
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = libsql_client.create_client(url=self.url, auth_token=self.auth_token)
            self._create_tables()
        return self._client

    def _create_tables(self):
        try:
            self._client.execute("""
                CREATE TABLE IF NOT EXISTS referusers (
                    user_id INTEGER PRIMARY KEY
                )
            """)
            self._client.execute("""
                CREATE TABLE IF NOT EXISTS refers (
                    user_id INTEGER PRIMARY KEY,
                    points INTEGER DEFAULT 0
                )
            """)
        except Exception as e:
            logger.error(f"Table creation error in refer: {e}")

    def add_user(self, user_id):
        if not self.is_user_in_list(user_id):
            self.client.execute("INSERT OR IGNORE INTO referusers (user_id) VALUES (?)", (int(user_id),))

    def remove_user(self, user_id):
        self.client.execute("DELETE FROM referusers WHERE user_id = ?", (int(user_id),))

    def is_user_in_list(self, user_id):
        res = self.client.execute("SELECT 1 FROM referusers WHERE user_id = ?", (int(user_id),))
        return len(list(res.rows)) > 0

    def add_refer_points(self, user_id: int, points: int):
        self.client.execute(
            "INSERT OR REPLACE INTO refers (user_id, points) VALUES (?, ?)",
            (int(user_id), int(points))
        )

    def get_refer_points(self, user_id: int):
        res = self.client.execute("SELECT points FROM refers WHERE user_id = ?", (int(user_id),))
        rows = list(res.rows)
        return rows[0][0] if rows and rows[0][0] is not None else 0

referdb = UserTracker(LIBSQL_URL, LIBSQL_AUTH_TOKEN)
