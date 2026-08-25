import logging
from struct import pack
import re
import base64
from pyrogram.file_id import FileId
from typing import Dict, List
from collections import defaultdict
import libsql_client
from info import *
from utils import get_settings, save_group_settings
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
#---------------------------------------------------------

class TursoDB:
    def __init__(self, url, auth_token):
        self.url = url
        self.auth_token = auth_token
        self._client = None

    async def get_client(self):
        if self._client is None:
            self._client = libsql_client.create_client(url=self.url, auth_token=self.auth_token)
            await self._create_tables()
        return self._client

    async def _create_tables(self):
        try:
            client = self._client
            await client.execute("""
                CREATE TABLE IF NOT EXISTS media (
                    file_id TEXT PRIMARY KEY,
                    file_ref TEXT,
                    file_name TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    file_type TEXT,
                    mime_type TEXT,
                    caption TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await client.execute("""
                CREATE TABLE IF NOT EXISTS media2 (
                    file_id TEXT PRIMARY KEY,
                    file_ref TEXT,
                    file_name TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    file_type TEXT,
                    mime_type TEXT,
                    caption TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        except Exception as e:
            logger.error(f"Media table creation error: {e}")

db_client = TursoDB(LIBSQL_URL, LIBSQL_AUTH_TOKEN)

class MediaRecord:
    def __init__(self, row):
        self.file_id = row[0]
        self.file_ref = row[1]
        self.file_name = row[2]
        self.file_size = row[3]
        self.file_type = row[4]
        self.mime_type = row[5]
        self.caption = row[6]

# Compatibility classes taaki bot.py ya plugins me import error na aaye
class Media:
    pass

class Media2:
    pass

async def save_file(media):
    """Save file in Turso database with duplicate checking."""
    file_id, file_ref = unpack_new_file_id(media.file_id)
    file_name = re.sub(r"[_\-\.#+$%^&*()!~`,;:\"'?/<>\[\]{}=|\\]", " ",
                       str(media.file_name))
    file_name = re.sub(r"\s+", " ", file_name).strip()
    
    table_name = "media"
    target_db = "Primary"
    
    client = await db_client.get_client()

    if MULTIPLE_DB:
        try:
            res = await client.execute("SELECT 1 FROM media WHERE file_id = ? LIMIT 1", (file_id,))
            if getattr(res, 'rows', None) and list(res.rows):
                logger.info(f"[SKIP] '{file_name}' already in Primary DB.")
                return False, 0
        except Exception as e:
            logger.error("Error during MULTIPLE_DB check; defaulting to primary DB.", exc_info=e)

    caption_text = (media.caption.html if media.caption and INDEX_CAPTION else None)

    try:
        await client.execute(f"""
            INSERT OR IGNORE INTO {table_name} 
            (file_id, file_ref, file_name, file_size, file_type, mime_type, caption) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (file_id, file_ref, file_name, media.file_size, media.file_type, media.mime_type, caption_text))
        
        logger.info(f"[SUCCESS] '{file_name}' saved to {target_db} DB.")
        return True, 1
    except Exception as e:
        logger.exception(f"[ERROR] Failed commit of '{file_name}' to {target_db} DB.", exc_info=e)
        return False, 3

async def get_search_results(chat_id, query, file_type=None, max_results=10, offset=0, filter=False):
    if chat_id is not None:
        settings = await get_settings(int(chat_id))
        try:
            max_results = 10 if settings.get("max_btn") else int(MAX_B_TN)
        except KeyError:
            await save_group_settings(int(chat_id), "max_btn", False)
            settings = await get_settings(int(chat_id))
            max_results = 10 if settings.get("max_btn") else int(MAX_B_TN)

    if max_results % 2:         
        max_results += 1

    if isinstance(query, list):
        search_terms = [q.strip() for q in query if q.strip()]
    else:
        search_terms = [query.strip()] if query.strip() else []

    client = await db_client.get_client()

    if not search_terms:
        sql_query = "SELECT file_id, file_ref, file_name, file_size, file_type, mime_type, caption FROM media"
        params = []
    else:
        conditions = []
        params = []
        for term in search_terms:
            like_term = f"%{term}%"
            if USE_CAPTION_FILTER:
                conditions.append("(file_name LIKE ? OR caption LIKE ?)")
                params.extend([like_term, like_term])
            else:
                conditions.append("file_name LIKE ?")
                params.append(like_term)
        
        where_clause = " OR ".join(conditions)
        sql_query = f"SELECT file_id, file_ref, file_name, file_size, file_type, mime_type, caption FROM media WHERE ({where_clause})"

    if file_type:
        if "WHERE" in sql_query:
            sql_query += " AND file_type = ?"
        else:
            sql_query += " WHERE file_type = ?"
        params.append(file_type)

    count_sql = sql_query.replace("SELECT file_id, file_ref, file_name, file_size, file_type, mime_type, caption", "SELECT COUNT(*)")
    total_res = await client.execute(count_sql, params)
    total_rows = getattr(total_res, 'rows', None) or []
    total_results = total_rows[0][0] if total_rows else 0

    sql_query += " ORDER BY rowid DESC LIMIT ? OFFSET ?"
    params.extend([max_results, offset])

    cursor1 = await client.execute(sql_query, params)
    rows1 = getattr(cursor1, 'rows', None) or []
    files1 = [MediaRecord(row) for row in rows1]

    files = files1
    if MULTIPLE_DB:
        remaining = max_results - len(files1)
        if remaining > 0:
            cursor2 = await client.execute(sql_query.replace("FROM media", "FROM media2"), params)
            rows2 = getattr(cursor2, 'rows', None) or []
            files2 = [MediaRecord(row) for row in rows2]
            files = files1 + files2

    next_offset = offset + len(files)
    if next_offset >= total_results:
        next_offset = ""
    return files, next_offset, total_results

async def get_bad_files(query, file_type=None, filter=False):
    query = query.strip()
    like_term = f"%{query}%" if query else "%"
    
    if USE_CAPTION_FILTER:
        sql = "SELECT file_id, file_ref, file_name, file_size, file_type, mime_type, caption FROM media WHERE file_name LIKE ? OR caption LIKE ?"
        params = [like_term, like_term]
    else:
        sql = "SELECT file_id, file_ref, file_name, file_size, file_type, mime_type, caption FROM media WHERE file_name LIKE ?"
        params = [like_term]

    if file_type:
        sql += " AND file_type = ?"
        params.append(file_type)

    sql += " ORDER BY rowid DESC"
    client = await db_client.get_client()
    cursor = await client.execute(sql, params)
    rows = getattr(cursor, 'rows', None) or []
    files = [MediaRecord(row) for row in rows]
    return files, len(files)

async def get_file_details(query):
    client = await db_client.get_client()
    cursor = await client.execute("SELECT file_id, file_ref, file_name, file_size, file_type, mime_type, caption FROM media WHERE file_id = ?", (query,))
    rows = getattr(cursor, 'rows', None) or []
    filedetails = [MediaRecord(row) for row in rows]
    if not filedetails and MULTIPLE_DB:
        cursor2 = await client.execute("SELECT file_id, file_ref, file_name, file_size, file_type, mime_type, caption FROM media2 WHERE file_id = ?", (query,))
        rows2 = getattr(cursor2, 'rows', None) or []
        filedetails = [MediaRecord(row) for row in rows2]
    return filedetails

def encode_file_id(s: bytes) -> str:
    r = b""
    n = 0
    for i in s + bytes([22]) + bytes([4]):
        if i == 0:
            n += 1
        else:
            if n:
                r += b"\x00" + bytes([n])
                n = 0

            r += bytes([i])
    return base64.urlsafe_b64encode(r).decode().rstrip("=")

def encode_file_ref(file_ref: bytes) -> str:
    return base64.urlsafe_b64encode(file_ref).decode().rstrip("=")

def unpack_new_file_id(new_file_id):
    decoded = FileId.decode(new_file_id)
    file_id = encode_file_id(
        pack(
            "<iiqq",
            int(decoded.file_type),
            decoded.dc_id,
            decoded.media_id,
            decoded.access_hash
        )
    )
    file_ref = encode_file_ref(decoded.file_reference)
    return file_id, file_ref

async def dreamxbotz_fetch_media(limit: int) -> List[object]:
    try:
        client = await db_client.get_client()
        cursor = await client.execute("SELECT file_id, file_ref, file_name, file_size, file_type, mime_type, caption FROM media ORDER BY rowid DESC LIMIT ?", (limit,))
        rows = getattr(cursor, 'rows', None) or []
        files = [MediaRecord(row) for row in rows]
        return files
    except Exception as e:
        logger.error(f"Error in dreamxbotz_fetch_media: {e}")
        return []

async def dreamxbotz_clean_title(filename: str, is_series: bool = False) -> str:
    try:
        year_match = re.search(r"^(.*?(\d{4}|\(\d{4}\)))", filename, re.IGNORECASE)
        if year_match:
            title = year_match.group(1).replace('(', '').replace(')', '') 
            return re.sub(r"(?:@[^ \n\r\t.,:;!?()\[\]{}<>\\\/\"'=_%]+|[._\-\[\]@()]+)", " ", title).strip().title()
        if is_series:
            season_match = re.search(r"(.*?)(?:S(\d{1,2})|Season\s*(\d+)|Season(\d+))(?:\s*Combined)?", filename, re.IGNORECASE)
            if season_match:
                title = season_match.group(1).strip()
                season = season_match.group(2) or season_match.group(3) or season_match.group(4)
                title = re.sub(r"(?:@[^ \n\r\t.,:;!?()\[\]{}<>\\\/\"'=_%]+|[._\-\[\]@()]+)", " ", title).strip().title()
                return f"{title} S{int(season):02}"
        title = filename
        return re.sub(r"(?:@[^ \n\r\t.,:;!?()\[\]{}<>\\\/\"'=_%]+|[._\-\[\]@()]+)", " ", title).strip().title()
    except Exception as e:
        logger.error(f"Error in truncate_title: {e}")
        return filename
        
async def dreamxbotz_get_movies(limit: int = 20) -> List[str]:
    try:
        cursor = await dreamxbotz_fetch_media(limit * 2)
        results = set()
        pattern = r"(?:s\d{1,2}|season\s*\d+|season\s*\d+)(?:\s*combined)?(?:e\d{1,2}|episode\s*\d+)?\b"
        for file in cursor:
            file_name = getattr(file, "file_name", "")
            if not re.search(pattern, file_name, re.IGNORECASE):
                title = await dreamxbotz_clean_title(file_name)
                results.add(title)
            if len(results) >= limit:
                break
        return sorted(list(results))[:limit]
    except Exception as e:
        logger.error(f"Error in dreamxbotz_get_movies: {e}")
        return []

async def dreamxbotz_get_series(limit: int = 30) -> Dict[str, List[int]]:
    try:
        cursor = await dreamxbotz_fetch_media(limit * 5)
        grouped = defaultdict(list)
        pattern = r"(.*?)(?:S(\d{1,2})|Season\s*(\d+)|Season(\d+))(?:\s*Combined)?(?:E(\d{1,2})|Episode\s*(\d+))?\b"
        for file in cursor:
            file_name = getattr(file, "file_name", "")
            match = re.search(pattern, file_name, re.IGNORECASE)
            if match:
                title = await dreamxbotz_clean_title(match.group(1), is_series=True)
                season = int(match.group(2) or match.group(3) or match.group(4))
                grouped[title].append(season)
        return {title: sorted(set(seasons))[:10] for title, seasons in grouped.items() if seasons}
    except Exception as e:
        logger.error(f"Error in dreamxbotz_get_series: {e}")
        return []
