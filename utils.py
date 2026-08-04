import asyncio
import re
import os
import math
from datetime import datetime, timedelta
import pytz
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram import Client, enums
from pyrogram.errors import UserNotParticipant, ChatAdminRequired, UserIsBlocked
from database.users_chats_db import db
from database.config_db import mdb
from Script import script
from info import *

# IMDb / Cinemagoer Initialization (Crash-Safe Fix)
try:
    from imdb import Cinemagoer
    imdb = Cinemagoer('http')
except Exception as e:
    try:
        from imdb import IMDb
        imdb = IMDb()
    except Exception:
        imdb = None

class Temp:
    U_NAME = None
    B_NAME = None
    B_LINK = None
    GETALL = {}
    SHORT = {}
    IMDB_CAP = {}

temp = Temp()

def get_size(size):
    if not size:
        return "0 B"
    size = int(size)
    suffixes = ['B', 'KB', 'MB', 'GB', 'TB']
    i = 0
    while size >= 1024 and i < len(suffixes) - 1:
        size /= 1024.0
        i += 1
    return f"{size:.2f} {suffixes[i]}"

def clean_filename(name):
    if not name:
        return ""
    name = re.sub(r'http\S+|www\.\S+|t\.me\/\S+', '', name)
    name = re.sub(r'[\._]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def generate_season_variations(query, season_number):
    s_num = str(season_number).zfill(2)
    variations = [
        f"{query} S{s_num}",
        f"{query} Season {season_number}",
        f"{query} S{season_number}"
    ]
    return variations

async def is_subscribed(client, query, fsub_channels):
    user_id = query.from_user.id
    buttons = []
    for channel in fsub_channels:
        try:
            member = await client.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in [
                enums.ChatMemberStatus.BANNED,
                enums.ChatMemberStatus.RESTRICTED,
            ]:
                continue
        except UserNotParticipant:
            try:
                chat = await client.get_chat(channel)
                invite_link = chat.invite_link or await client.export_chat_invite_link(channel)
                buttons.append([InlineKeyboardButton(f"📢 Join {chat.title}", url=invite_link)])
            except Exception:
                pass
        except Exception:
            pass
    return buttons

async def is_req_subscribed(client, query):
    if not AUTH_REQ_CHANNEL:
        return True
    user_id = query.from_user.id
    try:
        member = await client.get_chat_member(chat_id=int(AUTH_REQ_CHANNEL), user_id=user_id)
        if member.status in [
            enums.ChatMemberStatus.BANNED,
            enums.ChatMemberStatus.RESTRICTED,
        ]:
            return False
        return True
    except UserNotParticipant:
        return False
    except Exception:
        return True

async def is_check_admin(client, chat_id, user_id):
    if user_id in ADMINS:
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in [
            enums.ChatMemberStatus.ADMINISTRATOR,
            enums.ChatMemberStatus.OWNER,
        ]
    except Exception:
        return False

async def get_settings(chat_id):
    settings = await db.get_chat(chat_id)
    if not settings:
        settings = {
            'button': BUTTON_MODE,
            'file_secure': PROTECT_CONTENT,
            'imdb': IMDB,
            'welcome': MELCOW_NEW_USERS,
            'auto_delete': AUTO_DELETE,
            'max_btn': MAX_BTN,
            'spell_check': SPELL_CHECK_REPLY,
            'auto_ffilter': AUTO_FFILTER,
            'is_verify': IS_VERIFY
        }
        await save_group_settings(chat_id, settings=settings)
    return settings

async def save_group_settings(chat_id, key=None, value=None, settings=None):
    if settings:
        await db.update_chat(chat_id, settings)
    elif key is not None:
        curr_settings = await get_settings(chat_id)
        curr_settings[key] = value
        await db.update_chat(chat_id, curr_settings)

async def group_setting_buttons(grp_id):
    settings = await get_settings(grp_id)
    buttons = [
        [
            InlineKeyboardButton('ʀᴇꜱᴜʟᴛ ᴘᴀɢᴇ', callback_data=f'setgs#button#{settings.get("button")}#{str(grp_id)}'),
            InlineKeyboardButton('ʙᴜᴛᴛᴏɴ' if settings.get("button") else 'ᴛᴇxᴛ', callback_data=f'setgs#button#{settings.get("button")}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('ꜰɪʟᴇ ꜱᴇᴄᴜʀᴇ', callback_data=f'setgs#file_secure#{settings.get("file_secure", False)}#{str(grp_id)}'),
            InlineKeyboardButton('✔ Oɴ' if settings.get("file_secure", False) else '✘ Oғғ', callback_data=f'setgs#file_secure#{settings.get("file_secure", False)}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('ɪᴍᴅʙ ᴘᴏꜱᴛᴇʀ', callback_data=f'setgs#imdb#{settings.get("imdb", False)}#{str(grp_id)}'),
            InlineKeyboardButton('✔ Oɴ' if settings.get("imdb", False) else '✘ Oғғ', callback_data=f'setgs#imdb#{settings.get("imdb", False)}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ', callback_data=f'setgs#auto_delete#{settings.get("auto_delete", True)}#{str(grp_id)}'),
            InlineKeyboardButton('✔ Oɴ' if settings.get("auto_delete", True) else '✘ Oғғ', callback_data=f'setgs#auto_delete#{settings.get("auto_delete", True)}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('ꜱᴘᴇʟʟ ᴄʜᴇᴄᴋ', callback_data=f'setgs#spell_check#{settings.get("spell_check", True)}#{str(grp_id)}'),
            InlineKeyboardButton('✔ Oɴ' if settings.get("spell_check", True) else '✘ Oғғ', callback_data=f'setgs#spell_check#{settings.get("spell_check", True)}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('❌ Remove ❌', callback_data=f"removegrp#{grp_id}")
        ],
        [
            InlineKeyboardButton('⇋ ᴄʟᴏꜱᴇ ꜱᴇᴛᴛɪɴɢꜱ ᴍᴇɴᴜ ⇋', callback_data='close_data')
        ]
    ]
    return buttons

async def get_poster(query, bulk=False, id=False, file=None):
    if not imdb:
        return {}
    try:
        if id:
            movie = imdb.get_movie(query)
            return {
                'title': movie.get('title', ''),
                'votes': movie.get('votes', ''),
                'aka': movie.get('akas', [''])[0] if movie.get('akas') else '',
                'seasons': movie.get('number of seasons', ''),
                'box_office': movie.get('box office', ''),
                'localized_title': movie.get('localized title', ''),
                'kind': movie.get('kind', ''),
                'imdb_id': f"tt{movie.movieID}",
                'cast': ', '.join([item['name'] for item in movie.get('cast', [])[:3]]),
                'runtime': movie.get('runtimes', [''])[0] if movie.get('runtimes') else '',
                'countries': ', '.join(movie.get('countries', [])),
                'certificates': ', '.join(movie.get('certificates', [])),
                'languages': ', '.join(movie.get('languages', [])),
                'director': ', '.join([item['name'] for item in movie.get('director', [])]),
                'writer': ', '.join([item['name'] for item in movie.get('writer', [])]),
                'producer': ', '.join([item['name'] for item in movie.get('producer', [])]),
                'composer': ', '.join([item['name'] for item in movie.get('composer', [])]),
                'cinematographer': ', '.join([item['name'] for item in movie.get('cinematographer', [])]),
                'music_team': ', '.join([item['name'] for item in movie.get('music department', [])]),
                'distributors': ', '.join([item['name'] for item in movie.get('distributors', [])]),
                'release_date': movie.get('original air date', ''),
                'year': movie.get('year', ''),
                'genres': ', '.join(movie.get('genres', [])),
                'poster': movie.get('full-size cover url', ''),
                'plot': movie.get('plot outline', ''),
                'rating': movie.get('rating', ''),
                'url': f"https://www.imdb.com/title/tt{movie.movieID}"
            }
            
        results = imdb.search_movie(query)
        if not results:
            return {} if not bulk else []
        if bulk:
            return results[:5]
        
        movie = imdb.get_movie(results[0].movieID)
        return {
            'title': movie.get('title', ''),
            'votes': movie.get('votes', ''),
            'aka': movie.get('akas', [''])[0] if movie.get('akas') else '',
            'seasons': movie.get('number of seasons', ''),
            'box_office': movie.get('box office', ''),
            'localized_title': movie.get('localized title', ''),
            'kind': movie.get('kind', ''),
            'imdb_id': f"tt{movie.movieID}",
            'cast': ', '.join([item['name'] for item in movie.get('cast', [])[:3]]),
            'runtime': movie.get('runtimes', [''])[0] if movie.get('runtimes') else '',
            'countries': ', '.join(movie.get('countries', [])),
            'certificates': ', '.join(movie.get('certificates', [])),
            'languages': ', '.join(movie.get('languages', [])),
            'director': ', '.join([item['name'] for item in movie.get('director', [])]),
            'writer': ', '.join([item['name'] for item in movie.get('writer', [])]),
            'producer': ', '.join([item['name'] for item in movie.get('producer', [])]),
            'composer': ', '.join([item['name'] for item in movie.get('composer', [])]),
            'cinematographer': ', '.join([item['name'] for item in movie.get('cinematographer', [])]),
            'music_team': ', '.join([item['name'] for item in movie.get('music department', [])]),
            'distributors': ', '.join([item['name'] for item in movie.get('distributors', [])]),
            'release_date': movie.get('original air date', ''),
            'year': movie.get('year', ''),
            'genres': ', '.join(movie.get('genres', [])),
            'poster': movie.get('full-size cover url', ''),
            'plot': movie.get('plot outline', ''),
            'rating': movie.get('rating', ''),
            'url': f"https://www.imdb.com/title/tt{movie.movieID}"
        }
    except Exception as e:
        return {} if not bulk else []

async def get_cap(settings, remaining_seconds, files, query, total_results, search):
    cap = f"<b>Tʜᴇ Rᴇꜱᴜʟᴛꜱ Fᴏʀ ☞ {search}\n\nʀᴇsᴜʟᴛ sʜᴏᴡ ɪɴ ☞ {remaining_seconds} sᴇᴄᴏɴᴅs\n\n🍿 Yᴏᴜʀ Mᴏᴠɪᴇ Fɪʟᴇꜱ 👇\n\n</b>"
    if not settings.get('button'):
        for file in files:
            cap += f"<b>📁 {get_size(file.file_size)} ≽ <a href='https://telegram.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file.file_id}'>{clean_filename(file.file_name)}</a>\n\n</b>"
    return cap

def extract_request_content(text):
    if not text:
        return ""
    lines = text.split('\n')
    for line in lines:
        if "Message" in line or "Message :" in line:
            return line.split(':', 1)[-1].strip()
    return text.strip()

async def log_error(client, error_msg):
    try:
        await client.send_message(chat_id=LOG_CHANNEL, text=f"<b>#ERROR_LOG</b>\n\n<code>{error_msg}</code>")
    except Exception:
        pass
