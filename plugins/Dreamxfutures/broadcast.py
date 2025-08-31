
import datetime, time, os, asyncio,logging 
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.errors.exceptions.bad_request_400 import MessageTooLong
from database.users_chats_db import db
from info import ADMINS
from utils import users_broadcast, groups_broadcast, temp, get_readable_time, clear_junk, junk_group
import asyncio
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup 

lock = asyncio.Lock()

@Client.on_callback_query(filters.regex(r'^broadcast_cancel'))
async def broadcast_cancel(bot, query):
    _, ident = query.data.split("#")
    if ident == 'users':
        await query.message.edit("ᴛʀʏɪɴɢ ᴛᴏ ᴄᴀɴᴄᴇʟ ᴜsᴇʀs ʙʀᴏᴀᴅᴄᴀsᴛɪɴɢ...")
        temp.B_USERS_CANCEL = True
    elif ident == 'groups':
        temp.B_GROUPS_CANCEL = True
        await query.message.edit("ᴛʀʏɪɴɢ ᴛᴏ ᴄᴀɴᴄᴇʟ ɢʀᴏᴜᴘs ʙʀᴏᴀᴅᴄᴀsᴛɪɴɢ...")
       
@Client.on_message(filters.command("broadcast") & filters.user(ADMINS) & filters.reply)
async def broadcast_users(bot, message):
    if lock.locked():
        return await message.reply('Currently broadcast processing, Wait for complete.')

    p = await message.reply('<b>Do you want pin this message in users?</b>', reply_markup=ReplyKeyboardMarkup([['Yes', 'No']], one_time_keyboard=True, resize_keyboard=True))
    msg = await bot.listen(chat_id=message.chat.id, user_id=message.from_user.id)
    if msg.text == 'Yes':
        is_pin = True
    elif msg.text == 'No':
        is_pin = False
    else:
        await p.delete()
        return await message.reply_text('Wrong Response!')
    await p.delete()
    users = await db.get_all_users()
    b_msg = message.reply_to_message
    dreamxbotz_sts = await message.reply_text(text='<b>Bʀᴏᴀᴅᴄᴀsᴛɪɴɢ Yᴏᴜʀ Mᴇssᴀɢᴇs...⌛️</b>')
    start_time = time.time()
    total_users = await db.total_users_count()
    done = 0
    blocked = 0
    deleted = 0
    failed = 0
    success = 0
    async with lock:
        async for user in users:
            time_taken = get_readable_time(time.time()-start_time)
            if temp.B_USERS_CANCEL:
                temp.B_USERS_CANCEL = False
                await dreamxbotz_sts.edit(f"Users broadcast Cancelled!\nCompleted in {time_taken}\n\nTotal Users: <code>{total_users}</code>\nCompleted: <code>{done} / {total_users}</code>\nSuccess: <code>{success}</code>\nBʟᴏᴄᴋᴇᴅ: {blocked}\nDᴇʟᴇᴛᴇᴅ: {deleted}")
                return
            _, sts = await users_broadcast(int(user['id']), b_msg, is_pin)
            if sts == 'Success':
                success += 1
            if sts == "Blocked":
                blocked+=1
            elif sts == "Deleted":
                deleted += 1
            elif sts == 'Error':
                failed += 1
            done += 1
            if not done % 20:
                btn = [[
                    InlineKeyboardButton('CANCEL', callback_data=f'broadcast_cancel#users')
                ]]
                await dreamxbotz_sts.edit(f"Bʀᴏᴀᴅᴄᴀsᴛ Iɴ Pʀᴏɢʀᴇss:\n\nTᴏᴛᴀʟ Uꜱᴇʀꜱ {total_users}\nCᴏᴍᴩʟᴇᴛᴇᴅ: {done} / {total_users}\nSᴜᴄᴄᴇꜱꜱ: {success}\nBʟᴏᴄᴋᴇᴅ: {blocked}\nDᴇʟᴇᴛᴇᴅ: {deleted}", reply_markup=InlineKeyboardMarkup(btn))
        await dreamxbotz_sts.edit(f"Users broadcast completed.\nCompleted in {time_taken}\n\nTotal Users: <code>{total_users}</code>\nCompleted: <code>{done} / {total_users}</code>\nSuccess: <code>{success}</code>\nBʟᴏᴄᴋᴇᴅ: {blocked}\nDᴇʟᴇᴛᴇᴅ: {deleted}")

@Client.on_message(filters.command("grp_broadcast") & filters.user(ADMINS) & filters.reply)
async def broadcast_group(bot, message):
    p = await message.reply('<b>Do you want pin this message in groups?</b>', reply_markup=ReplyKeyboardMarkup([['Yes', 'No']], one_time_keyboard=True, resize_keyboard=True))
    msg = await bot.listen(chat_id=message.chat.id, user_id=message.from_user.id)
    if msg.text == 'Yes':
        is_pin = True
    elif msg.text == 'No':
        is_pin = False
    else:
        await p.delete()
        return await message.reply_text('Wrong Response!')
    await p.delete()
    chats = await db.get_all_chats()
    b_msg = message.reply_to_message
    dreamxbotz_sts = await message.reply_text(text='<b>Bʀᴏᴀᴅᴄᴀsᴛɪɴɢ Yᴏᴜʀ Mᴇssᴀɢᴇs...⏳</b>')
    start_time = time.time()
    total_chats = await db.total_chat_count()
    done = 0
    failed = 0
    success = 0
    async with lock:
        async for chat in chats:
            time_taken = get_readable_time(time.time()-start_time)
            if temp.B_GROUPS_CANCEL:
                temp.B_GROUPS_CANCEL = False
                await dreamxbotz_sts.edit(f"Groups broadcast Cancelled!\nCompleted in {time_taken}\n\nTotal Groups: <code>{total_chats}</code>\nCompleted: <code>{done} / {total_chats}</code>\nSuccess: <code>{success}</code>\nFailed: <code>{failed}</code>")
                return
            sts = await groups_broadcast(int(chat['id']), b_msg, is_pin)
            if sts == 'Success':
                success += 1
            elif sts == 'Error':
                failed += 1
            done += 1
            if not done % 10:
                btn = [[
                    InlineKeyboardButton('CANCEL', callback_data=f'broadcast_cancel#groups')
                ]]
                await dreamxbotz_sts.edit(f"Gʀᴏᴜᴘ ʙʀᴏᴀᴅᴄᴀsᴛ ɪɴ ᴘʀᴏɢʀᴇss...\n\nTotal Groups: <code>{total_chats}</code>\nCompleted: <code>{done} / {total_chats}</code>\nSuccess: <code>{success}</code>\nFailed: <code>{failed}</code>", reply_markup=InlineKeyboardMarkup(btn))  
        try:         
            await dreamxbotz_sts.edit(f"Gʀᴏᴜᴘ ʙʀᴏᴀᴅᴄᴀsᴛ ᴄᴏᴍᴘʟᴇᴛᴇᴅ.\nCompleted in {time_taken}\n\nTotal Groups: <code>{total_chats}</code>\nCompleted: <code>{done} / {total_chats}</code>\nSuccess: <code>{success}</code>\nFailed: <code>{failed}</code>")
        except MessageTooLong:
            with open('reason.txt', 'w+') as outfile:
                outfile.write(failed)
            await message.reply_document('reason.txt', caption=f"Completed:\nCompleted in {time_taken} seconds.\n\nTotal Groups {total_chats}\nCompleted: {done} / {total_chats}\nSuccess: {success}")
            os.remove("reason.txt")

@Client.on_message(filters.command("clear_junk") & filters.user(ADMINS))
async def remove_junkuser__db(bot, message):
    users = await db.get_all_users()
    b_msg = message 
    sts = await message.reply_text('ɪɴ ᴘʀᴏɢʀᴇss.... ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ')   
    start_time = time.time()
    total_users = await db.total_users_count()
    blocked = 0
    deleted = 0
    failed = 0
    done = 0
    async for user in users:
        pti, sh = await clear_junk(int(user['id']), b_msg)
        if pti == False:
            if sh == "Blocked":
                blocked+=1
            elif sh == "Deleted":
                deleted += 1
            elif sh == "Error":
                failed += 1
        done += 1
        if not done % 50:
            await sts.edit(f"In Progress:\n\nTotal Users {total_users}\nCompleted: {done} / {total_users}\nBlocked: {blocked}\nDeleted: {deleted}")    
    time_taken = datetime.timedelta(seconds=int(time.time()-start_time))
    await sts.delete()
    await bot.send_message(message.chat.id, f"Completed:\nCompleted in {time_taken} seconds.\n\nTotal Users {total_users}\nCompleted: {done} / {total_users}\nBlocked: {blocked}\nDeleted: {deleted}")

@Client.on_message(filters.command(["junk_group", "clear_junk_group"]) & filters.user(ADMINS))
async def junk_clear_group(bot, message):
    groups = await db.get_all_chats()
    if not groups:
        grp = await message.reply_text("❌ Nᴏ ɢʀᴏᴜᴘs ғᴏᴜɴᴅ ғᴏʀ ᴄʟᴇᴀʀ Jᴜɴᴋ ɢʀᴏᴜᴘs.")
        await asyncio.sleep(60)
        await grp.delete()
        return
    b_msg = message
    sts = await message.reply_text(text='..............')
    start_time = time.time()
    total_groups = await db.total_chat_count()
    done = 0
    failed = ""
    deleted = 0
    async for group in groups:
        pti, sh, ex = await junk_group(int(group['id']), b_msg)        
        if pti == False:
            if sh == "deleted":
                deleted+=1 
                failed += ex 
                try:
                    await bot.leave_chat(int(group['id']))
                except Exception as e:
                    print(f"{e} > {group['id']}")  
        done += 1
        if not done % 50:
            await sts.edit(f"in progress:\n\nTotal Groups {total_groups}\nCompleted: {done} / {total_groups}\nDeleted: {deleted}")    
    time_taken = datetime.timedelta(seconds=int(time.time()-start_time))
    await sts.delete()
    try:
        await bot.send_message(message.chat.id, f"Completed:\nCompleted in {time_taken} seconds.\n\nTotal Groups {total_groups}\nCompleted: {done} / {total_groups}\nDeleted: {deleted}\n\nFiled Reson:- {failed}")    
    except MessageTooLong:
        with open('junk.txt', 'w+') as outfile:
            outfile.write(failed)
        await message.reply_document('junk.txt', caption=f"Completed:\nCompleted in {time_taken} seconds.\n\nTotal Groups {total_groups}\nCompleted: {done} / {total_groups}\nDeleted: {deleted}")
        os.remove("junk.txt")
