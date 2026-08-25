import datetime
import pytz
import json
import libsql_client
from info import *

class Database:    
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
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    ban_status TEXT
                )
            """)
            await client.execute("""
                CREATE TABLE IF NOT EXISTS groups (
                    id INTEGER PRIMARY KEY,
                    title TEXT,
                    chat_status TEXT,
                    settings TEXT
                )
            """)
            await client.execute("""
                CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY
                )
            """)
            await client.execute("""
                CREATE TABLE IF NOT EXISTS bot_settings (
                    id INTEGER,
                    key TEXT,
                    value TEXT,
                    PRIMARY KEY (id, key)
                )
            """)
            await client.execute("""
                CREATE TABLE IF NOT EXISTS misc (
                    user_id INTEGER PRIMARY KEY,
                    last_verified TEXT,
                    second_time_verified TEXT,
                    third_time_verified TEXT
                )
            """)
            await client.execute("""
                CREATE TABLE IF NOT EXISTS verify_id (
                    user_id INTEGER,
                    hash TEXT,
                    verified INTEGER,
                    PRIMARY KEY (user_id, hash)
                )
            """)
            await client.execute("""
                CREATE TABLE IF NOT EXISTS premium_users (
                    id INTEGER PRIMARY KEY,
                    expiry_time TEXT,
                    has_free_trial INTEGER
                )
            """)
            await client.execute("""
                CREATE TABLE IF NOT EXISTS connections (
                    user_id INTEGER PRIMARY KEY,
                    group_ids TEXT
                )
            """)
            await client.execute("""
                CREATE TABLE IF NOT EXISTS movie_updates (
                    filename TEXT PRIMARY KEY
                )
            """)
        except Exception as e:
            print(f"Table creation error: {e}")

    async def add_name(self, filename):
        try:
            client = await self.get_client()
            res = await client.execute("SELECT 1 FROM movie_updates WHERE filename = ?", (filename,))
            if list(res.rows):
                return False
            await client.execute("INSERT INTO movie_updates (filename) VALUES (?)", (filename,))
            return True
        except Exception:
            return False

    async def delete_all_msg(self):
        client = await self.get_client()
        await client.execute("DELETE FROM movie_updates")
        print("All filenames notification have been deleted.")
        return True
 
    async def find_join_req(self, id):
        client = await self.get_client()
        res = await client.execute("SELECT 1 FROM requests WHERE id = ?", (id,))
        return len(list(res.rows)) > 0
     
    async def add_join_req(self, id):
        client = await self.get_client()
        await client.execute("INSERT OR IGNORE INTO requests (id) VALUES (?)", (id,))

    async def del_join_req(self):
        client = await self.get_client()
        await client.execute("DELETE FROM requests")

    def new_user(self, id, name):
        return dict(
            id=id,
            name=name,
            ban_status=dict(
                is_banned=False,
                ban_reason="",
            ),
        )

    def new_group(self, id, title):
        return dict(
            id=id,
            title=title,
            chat_status=dict(
                is_disabled=False,
                reason="",
            ),
        )
    
    async def add_user(self, id, name):
        if not await self.is_user_exist(id):
            client = await self.get_client()
            ban_status = json.dumps({"is_banned": False, "ban_reason": ""})
            await client.execute("INSERT OR REPLACE INTO users (id, name, ban_status) VALUES (?, ?, ?)", (id, name, ban_status))
    
    async def is_user_exist(self, id):
        client = await self.get_client()
        res = await client.execute("SELECT 1 FROM users WHERE id = ?", (int(id),))
        return len(list(res.rows)) > 0
    
    async def total_users_count(self):
        client = await self.get_client()
        res = await client.execute("SELECT COUNT(*) FROM users")
        return list(res.rows)[0][0]
    
    async def remove_ban(self, id):
        client = await self.get_client()
        ban_status = json.dumps({"is_banned": False, "ban_reason": ""})
        await client.execute("UPDATE users SET ban_status = ? WHERE id = ?", (ban_status, int(id)))
    
    async def ban_user(self, user_id, ban_reason="No Reason"):
        client = await self.get_client()
        ban_status = json.dumps({"is_banned": True, "ban_reason": ban_reason})
        await client.execute("UPDATE users SET ban_status = ? WHERE id = ?", (ban_status, int(user_id)))

    async def get_ban_status(self, id):
        client = await self.get_client()
        default = dict(is_banned=False, ban_reason='')
        res = await client.execute("SELECT ban_status FROM users WHERE id = ?", (int(id),))
        rows = list(res.rows)
        if not rows or not rows[0][0]:
            return default
        try:
            return json.loads(rows[0][0])
        except Exception:
            return default

    async def get_all_users(self):
        client = await self.get_client()
        res = await client.execute("SELECT id, name, ban_status FROM users")
        class CursorMock:
            def __init__(self, rows):
                self.rows = rows
            async def __aiter__(self):
                for row in self.rows:
                    yield {"id": row[0], "name": row[1], "ban_status": json.loads(row[2]) if row[2] else {}}
        return CursorMock(res.rows)
    
    async def delete_user(self, user_id):
        client = await self.get_client()
        await client.execute("DELETE FROM users WHERE id = ?", (int(user_id),))
        
    async def delete_chat(self, id):
        client = await self.get_client()
        await client.execute("DELETE FROM groups WHERE id = ?", (int(id),))    

    async def get_banned(self):
        client = await self.get_client()
        res_u = await client.execute("SELECT id, ban_status FROM users")
        b_users = []
        for r in res_u.rows:
            try:
                bs = json.loads(r[1]) if r[1] else {}
                if bs.get('is_banned'):
                    b_users.append(r[0])
            except Exception:
                pass

        res_c = await client.execute("SELECT id, chat_status FROM groups")
        b_chats = []
        for r in res_c.rows:
            try:
                cs = json.loads(r[1]) if r[1] else {}
                if cs.get('is_disabled'):
                    b_chats.append(r[0])
            except Exception:
                pass
        return b_users, b_chats
    
    async def add_chat(self, chat, title):
        client = await self.get_client()
        chat_status = json.dumps({"is_disabled": False, "reason": ""})
        await client.execute("INSERT OR REPLACE INTO groups (id, title, chat_status) VALUES (?, ?, ?)", (int(chat), title, chat_status))
    
    async def get_chat(self, chat):
        client = await self.get_client()
        res = await client.execute("SELECT chat_status FROM groups WHERE id = ?", (int(chat),))
        rows = list(res.rows)
        if not rows or not rows[0][0]:
            return False
        try:
            return json.loads(rows[0][0])
        except Exception:
            return False
    
    async def re_enable_chat(self, id):
        client = await self.get_client()
        chat_status = json.dumps({"is_disabled": False, "reason": ""})
        await client.execute("UPDATE groups SET chat_status = ? WHERE id = ?", (chat_status, int(id)))
        
    async def update_settings(self, id, settings):
        client = await self.get_client()
        settings_str = json.dumps(settings)
        await client.execute("UPDATE groups SET settings = ? WHERE id = ?", (settings_str, int(id)))
                                  
    async def get_settings(self, id):
        client = await self.get_client()
        default = {
            'button': BUTTON_MODE,
            'botpm': P_TTI_SHOW_OFF,
            'file_secure': PROTECT_CONTENT,
            'imdb': IMDB,
            'spell_check': SPELL_CHECK_REPLY,
            'welcome': MELCOW_NEW_USERS,
            'auto_delete': AUTO_DELETE,
            'auto_ffilter': AUTO_FFILTER,
            'max_btn': MAX_BTN,
            'template': IMDB_TEMPLATE,
            'log': LOG_VR_CHANNEL,
            'tutorial': TUTORIAL,
            'tutorial_2': TUTORIAL_2,
            'tutorial_3': TUTORIAL_3,
            'shortner': SHORTENER_WEBSITE,
            'api': SHORTENER_API,
            'shortner_two': SHORTENER_WEBSITE2,
            'api_two': SHORTENER_API2,
            'shortner_three': SHORTENER_WEBSITE3,
            'api_three': SHORTENER_API3,
            'is_verify': IS_VERIFY,
            'verify_time': TWO_VERIFY_GAP,
            'third_verify_time': THREE_VERIFY_GAP,
            'caption': CUSTOM_FILE_CAPTION,
            'fsub': AUTH_CHANNELS
        }
        res = await client.execute("SELECT settings FROM groups WHERE id = ?", (int(id),))
        rows = list(res.rows)
        if rows and rows[0][0]:
            try:
                return json.loads(rows[0][0])
            except Exception:
                return default.copy()
        else:
            return default.copy()

    async def dreamx_reset_settings(self):
        try:
            client = await self.get_client()
            res = await client.execute("SELECT id, settings FROM groups")
            count = 0
            for r in res.rows:
                if r[1]:
                    await client.execute("UPDATE groups SET settings = NULL WHERE id = ?", (r[0],))
                    count += 1
            return count
        except Exception as e:
            print(f"Error deleting settings for all groups: {str(e)}")
            raise

    async def disable_chat(self, chat, reason="No Reason"):
        client = await self.get_client()
        chat_status = json.dumps({"is_disabled": True, "reason": reason})
        await client.execute("UPDATE groups SET chat_status = ? WHERE id = ?", (chat_status, int(chat)))

    async def total_chat_count(self):
        client = await self.get_client()
        res = await client.execute("SELECT COUNT(*) FROM groups")
        return list(res.rows)[0][0]
    
    async def get_all_chats(self):
        client = await self.get_client()
        res = await client.execute("SELECT id, title, chat_status, settings FROM groups")
        class CursorMock:
            def __init__(self, rows):
                self.rows = rows
            async def __aiter__(self):
                for row in self.rows:
                    yield {"id": row[0], "title": row[1], "chat_status": json.loads(row[2]) if row[2] else {}, "settings": json.loads(row[3]) if row[3] else {}}
        return CursorMock(res.rows)

    async def get_db_size(self):
        return 0

    async def get_user(self, user_id):
        client = await self.get_client()
        res = await client.execute("SELECT id, expiry_time, has_free_trial FROM premium_users WHERE id = ?", (int(user_id),))
        rows = list(res.rows)
        if not rows:
            return None
        return {
            "id": rows[0][0],
            "expiry_time": datetime.datetime.fromisoformat(rows[0][1]) if rows[0][1] else None,
            "has_free_trial": bool(rows[0][2])
        }

    async def update_user(self, user_data):
        client = await self.get_client()
        uid = int(user_data["id"])
        exp = user_data.get("expiry_time")
        exp_str = exp.isoformat() if isinstance(exp, datetime.datetime) else None
        trial = 1 if user_data.get("has_free_trial") else 0
        await client.execute("INSERT OR REPLACE INTO premium_users (id, expiry_time, has_free_trial) VALUES (?, ?, ?)", (uid, exp_str, trial))
  
    async def get_notcopy_user(self, user_id):
        client = await self.get_client()
        user_id = int(user_id)
        res = await client.execute("SELECT last_verified, second_time_verified, third_time_verified FROM misc WHERE user_id = ?", (user_id,))
        rows = list(res.rows)
        ist_timezone = pytz.timezone('Asia/Kolkata')
        if not rows:
            lv = datetime.datetime(2020, 5, 17, 0, 0, 0, tzinfo=ist_timezone).isoformat()
            stv = datetime.datetime(2019, 5, 17, 0, 0, 0, tzinfo=ist_timezone).isoformat()
            ttv = datetime.datetime(2018, 5, 17, 0, 0, 0, tzinfo=ist_timezone).isoformat()
            await client.execute("INSERT OR REPLACE INTO misc (user_id, last_verified, second_time_verified, third_time_verified) VALUES (?, ?, ?, ?)", (user_id, lv, stv, ttv))
            return {
                "user_id": user_id,
                "last_verified": datetime.datetime(2020, 5, 17, 0, 0, 0, tzinfo=ist_timezone),
                "second_time_verified": datetime.datetime(2019, 5, 17, 0, 0, 0, tzinfo=ist_timezone),
                "third_time_verified": datetime.datetime(2018, 5, 17, 0, 0, 0, tzinfo=ist_timezone)
            }
        else:
            r = rows[0]
            return {
                "user_id": user_id,
                "last_verified": datetime.datetime.fromisoformat(r[0]) if r[0] else datetime.datetime(2020, 5, 17, 0, 0, 0, tzinfo=ist_timezone),
                "second_time_verified": datetime.datetime.fromisoformat(r[1]) if r[1] else datetime.datetime(2019, 5, 17, 0, 0, 0, tzinfo=ist_timezone),
                "third_time_verified": datetime.datetime.fromisoformat(r[2]) if r[2] else datetime.datetime(2018, 5, 17, 0, 0, 0, tzinfo=ist_timezone)
            }

    async def update_notcopy_user(self, user_id, value: dict):
        client = await self.get_client()
        user_id = int(user_id)
        current = await self.get_notcopy_user(user_id)
        lv = value.get("last_verified", current["last_verified"])
        stv = value.get("second_time_verified", current["second_time_verified"])
        ttv = value.get("third_time_verified", current.get("third_time_verified", datetime.datetime(2018, 5, 17, 0, 0, 0, tzinfo=pytz.timezone('Asia/Kolkata'))))
        
        lv_str = lv.isoformat() if isinstance(lv, datetime.datetime) else lv
        stv_str = stv.isoformat() if isinstance(stv, datetime.datetime) else stv
        ttv_str = ttv.isoformat() if isinstance(ttv, datetime.datetime) else ttv
        
        await client.execute("INSERT OR REPLACE INTO misc (user_id, last_verified, second_time_verified, third_time_verified) VALUES (?, ?, ?, ?)", (user_id, lv_str, stv_str, ttv_str))
        return True

    async def is_user_verified(self, user_id):
        user = await self.get_notcopy_user(user_id)
        pastDate = user["last_verified"]
        ist_timezone = pytz.timezone('Asia/Kolkata')
        pastDate = pastDate.astimezone(ist_timezone)
        current_time = datetime.datetime.now(tz=ist_timezone)
        seconds_since_midnight = (current_time - datetime.datetime(current_time.year, current_time.month, current_time.day, 0, 0, 0, tzinfo=ist_timezone)).total_seconds()
        time_diff = current_time - pastDate
        total_seconds = time_diff.total_seconds()
        return total_seconds <= seconds_since_midnight

    async def user_verified(self, user_id):
        user = await self.get_notcopy_user(user_id)
        pastDate = user["second_time_verified"]
        ist_timezone = pytz.timezone('Asia/Kolkata')
        pastDate = pastDate.astimezone(ist_timezone)
        current_time = datetime.datetime.now(tz=ist_timezone)
        seconds_since_midnight = (current_time - datetime.datetime(current_time.year, current_time.month, current_time.day, 0, 0, 0, tzinfo=ist_timezone)).total_seconds()
        time_diff = current_time - pastDate
        total_seconds = time_diff.total_seconds()
        return total_seconds <= seconds_since_midnight

    async def use_second_shortener(self, user_id, time):
        user = await self.get_notcopy_user(user_id)
        if not user.get("second_time_verified"):
            ist_timezone = pytz.timezone('Asia/Kolkata')
            await self.update_notcopy_user(user_id, {"second_time_verified": datetime.datetime(2019, 5, 17, 0, 0, 0, tzinfo=ist_timezone)})
            user = await self.get_notcopy_user(user_id)
        if await self.is_user_verified(user_id):
            pastDate = user["last_verified"]
            ist_timezone = pytz.timezone('Asia/Kolkata')
            pastDate = pastDate.astimezone(ist_timezone)
            current_time = datetime.datetime.now(tz=ist_timezone)
            time_difference = current_time - pastDate
            if time_difference > datetime.timedelta(seconds=time):
                pastDate = user["last_verified"].astimezone(ist_timezone)
                second_time = user["second_time_verified"].astimezone(ist_timezone)
                return second_time < pastDate
        return False

    async def use_third_shortener(self, user_id, time):
        user = await self.get_notcopy_user(user_id)
        if not user.get("third_time_verified"):
            ist_timezone = pytz.timezone('Asia/Kolkata')
            await self.update_notcopy_user(user_id, {"third_time_verified": datetime.datetime(2018, 5, 17, 0, 0, 0, tzinfo=ist_timezone)})
            user = await self.get_notcopy_user(user_id)
        if await self.user_verified(user_id):
            pastDate = user["second_time_verified"]
            ist_timezone = pytz.timezone('Asia/Kolkata')
            pastDate = pastDate.astimezone(ist_timezone)
            current_time = datetime.datetime.now(tz=ist_timezone)
            time_difference = current_time - pastDate
            if time_difference > datetime.timedelta(seconds=time):
                pastDate = user["second_time_verified"].astimezone(ist_timezone)
                second_time = user["third_time_verified"].astimezone(ist_timezone)
                return second_time < pastDate
        return False
   
    async def create_verify_id(self, user_id: int, hash):
        client = await self.get_client()
        await client.execute("INSERT OR REPLACE INTO verify_id (user_id, hash, verified) VALUES (?, ?, 0)", (user_id, hash))
        return True

    async def get_verify_id_info(self, user_id: int, hash):
        client = await self.get_client()
        res = await client.execute("SELECT user_id, hash, verified FROM verify_id WHERE user_id = ? AND hash = ?", (user_id, hash))
        rows = list(res.rows)
        if not rows:
            return None
        return {"user_id": rows[0][0], "hash": rows[0][1], "verified": bool(rows[0][2])}

    async def update_verify_id_info(self, user_id, hash, value: dict):
        client = await self.get_client()
        v = 1 if value.get("verified") else 0
        await client.execute("UPDATE verify_id SET verified = ? WHERE user_id = ? AND hash = ?", (v, user_id, hash))
        return True
        
    async def has_premium_access(self, user_id):
        client = await self.get_client()
        user_data = await self.get_user(user_id)
        if user_data:
            expiry_time = user_data.get("expiry_time")
            if expiry_time is None:
                return False
            elif isinstance(expiry_time, datetime.datetime) and datetime.datetime.now() <= expiry_time:
                return True
            else:
                await client.execute("UPDATE premium_users SET expiry_time = NULL WHERE id = ?", (int(user_id),))
        return False

    async def update_one(self, filter_query, update_data):
        try:
            client = await self.get_client()
            uid = filter_query.get("id")
            if "$set" in update_data:
                for k, v in update_data["$set"].items():
                    if k == "expiry_time":
                        v_str = v.isoformat() if isinstance(v, datetime.datetime) else None
                        await client.execute("UPDATE premium_users SET expiry_time = ? WHERE id = ?", (v_str, int(uid)))
            return True
        except Exception as e:
            print(f"Error updating document: {e}")
            return False

    async def get_expired(self, current_time):
        client = await self.get_client()
        expired_users = []
        res = await client.execute("SELECT id, expiry_time, has_free_trial FROM premium_users WHERE expiry_time IS NOT NULL")
        for r in res.rows:
            if r[1]:
                exp = datetime.datetime.fromisoformat(r[1])
                if exp < current_time:
                    expired_users.append({"id": r[0], "expiry_time": exp, "has_free_trial": bool(r[2])})
        return expired_users

    async def remove_premium_access(self, user_id):
        client = await self.get_client()
        await client.execute("UPDATE premium_users SET expiry_time = NULL WHERE id = ?", (int(user_id),))
        return True

    async def check_trial_status(self, user_id):
        user_data = await self.get_user(user_id)
        if user_data:
            return user_data.get("has_free_trial", False)
        return False

    async def give_free_trial(self, user_id):
        client = await self.get_client()
        seconds = 5 * 60         
        expiry_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
        exp_str = expiry_time.isoformat()
        await client.execute("INSERT OR REPLACE INTO premium_users (id, expiry_time, has_free_trial) VALUES (?, ?, 1)", (int(user_id), exp_str))
        
    async def all_premium_users(self):
        client = await self.get_client()
        res = await client.execute("SELECT expiry_time FROM premium_users WHERE expiry_time IS NOT NULL")
        now = datetime.datetime.now()
        count = 0
        for r in res.rows:
            if r[0]:
                exp = datetime.datetime.fromisoformat(r[0])
                if exp > now:
                    count += 1
        return count
    
    async def get_bot_setting(self, bot_id, setting_key, default_value):
        client = await self.get_client()
        res = await client.execute("SELECT value FROM bot_settings WHERE id = ? AND key = ?", (int(bot_id), setting_key))
        rows = list(res.rows)
        if not rows:
            return default_value
        try:
            return json.loads(rows[0][0])
        except Exception:
            return rows[0][0]
        
    async def update_bot_setting(self, bot_id, setting_key, value):
        client = await self.get_client()
        val_str = json.dumps(value)
        await client.execute("INSERT OR REPLACE INTO bot_settings (id, key, value) VALUES (?, ?, ?)", (int(bot_id), setting_key, val_str))

    async def connect_group(self, group_id, user_id):
        client = await self.get_client()
        res = await client.execute("SELECT group_ids FROM connections WHERE user_id = ?", (int(user_id),))
        rows = list(res.rows)
        if rows and rows[0][0]:
            try:
                g_list = json.loads(rows[0][0])
            except Exception:
                g_list = []
            if group_id not in g_list:
                g_list.append(group_id)
                await client.execute("UPDATE connections SET group_ids = ? WHERE user_id = ?", (json.dumps(g_list), int(user_id)))
        else:
            await client.execute("INSERT OR REPLACE INTO connections (user_id, group_ids) VALUES (?, ?)", (int(user_id), json.dumps([group_id])))

    async def get_connected_grps(self, user_id):
        client = await self.get_client()
        res = await client.execute("SELECT group_ids FROM connections WHERE user_id = ?", (int(user_id),))
        rows = list(res.rows)
        if rows and rows[0][0]:
            try:
                return json.loads(rows[0][0])
            except Exception:
                return []
        return []
        
    async def remove_group_connection(self, group_id, user_id):
        client = await self.get_client()
        res = await client.execute("SELECT group_ids FROM connections WHERE user_id = ?", (int(user_id),))
        rows = list(res.rows)
        if rows and rows[0][0]:
            try:
                g_list = json.loads(rows[0][0])
                if group_id in g_list:
                    g_list.remove(group_id)
                    await client.execute("UPDATE connections SET group_ids = ? WHERE user_id = ?", (json.dumps(g_list), int(user_id)))
            except Exception:
                pass

    async def pm_search_status(self, bot_id):
        return await self.get_bot_setting(bot_id, 'PM_SEARCH', PM_SEARCH)

    async def update_pm_search_status(self, bot_id, enable):
        await self.update_bot_setting(bot_id, 'PM_SEARCH', enable)

    async def movie_update_status(self, bot_id):
        return await self.get_bot_setting(bot_id, 'MOVIE_UPDATE_NOTIFICATION', MOVIE_UPDATE_NOTIFICATION)

    async def update_movie_update_status(self, bot_id, enable):
        await self.update_bot_setting(bot_id, 'MOVIE_UPDATE_NOTIFICATION', enable)
     
db = Database(LIBSQL_URL, LIBSQL_AUTH_TOKEN)    
db2 = Database(LIBSQL_URL, LIBSQL_AUTH_TOKEN)
