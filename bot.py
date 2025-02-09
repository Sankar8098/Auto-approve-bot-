import os
import asyncio
import datetime
import time
from pyrogram.errors import InputUserDeactivated, UserNotParticipant, FloodWait, UserIsBlocked, PeerIdInvalid
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from motor.motor_asyncio import AsyncIOMotorClient

# Bot messages
ACCEPTED_TEXT = "Hey {user}\n\nYour Request For {chat} Is Accepted ✅"
START_TEXT = "Hai {}\n\nI am Auto Request Accept Bot With Working For All Channel. Add Me In Your Channel To Use"

# Environment variables
API_ID = int(os.environ.get('API_ID'))
API_HASH = os.environ.get('API_HASH')
BOT_TOKEN = os.environ.get('BOT_TOKEN')
DB_URL = os.environ.get('DB_URL')
ADMINS = list(map(int, os.environ.get('ADMINS').split(',')))

# Database client
Dbclient = AsyncIOMotorClient(DB_URL)
Cluster = Dbclient['Cluster0']
Data = Cluster['users']
Bot = Client(name='AutoAcceptBot', api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Initial chunk size for broadcast
CHUNK_SIZE = 100

async def send_message(user_id, b_msg):
    try:
        await b_msg.copy(chat_id=user_id)
        return 1, 0  # success, failure
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await send_message(user_id, b_msg)
    except (InputUserDeactivated, PeerIdInvalid):
        await Data.delete_many({'id': user_id})
        return 0, 1  # success, failure
    except UserIsBlocked:
        return 0, 1  # success, failure
    except Exception as e:
        print(f"Error sending message to {user_id}: {e}")
        return 0, 1  # success, failure

async def broadcast_messages(b_msg, sts, users, total_users):
    done = 0
    success = 0
    failed = 0
    start_time = time.time()

    for i in range(0, total_users, CHUNK_SIZE):
        chunk = users[i:i + CHUNK_SIZE]
        tasks = [send_message(int(user['id']), b_msg) for user in chunk]
        results = await asyncio.gather(*tasks)

        for res in results:
            s, f = res
            success += s
            failed += f
            done += 1

        await sts.edit(f"Broadcast in progress:\n\nTotal Users {total_users}\nCompleted: {done} / {total_users}\nSuccess: {success}\nFailed: {failed}")

    time_taken = datetime.timedelta(seconds=int(time.time() - start_time))
    await sts.delete()
    return done, success, failed, time_taken

@Bot.on_message(filters.command(["broadcast", "users"]) & filters.user(ADMINS))
async def broadcast(c, m):
    if m.text == "/users":
        total_users = await Data.count_documents({})
        return await m.reply(f"Total Users: {total_users}")
    b_msg = m.reply_to_message
    sts = await m.reply_text("Broadcasting your messages...")
    users_cursor = Data.find({})
    total_users = await Data.count_documents({})
    users = await users_cursor.to_list(length=total_users)

    done, success, failed, time_taken = await broadcast_messages(b_msg, sts, users, total_users)

    await m.reply_text(f"Broadcast Completed:\nCompleted in {time_taken} seconds.\n\nTotal Users {total_users}\nCompleted: {done} / {total_users}\nSuccess: {success}\nFailed: {failed}", quote=True)

@Bot.on_message(filters.command("start") & filters.private)
async def start_handler(c, m):
    user_id = m.from_user.id
    if not await Data.find_one({'id': user_id}):
        await Data.insert_one({'id': user_id})
    button = [[
        InlineKeyboardButton('Updates', url='https://t.me/TN_Bots'),
        InlineKeyboardButton('Support', url='https://t.me/TN_Bots')
    ]]
    return await m.reply_text(text=START_TEXT.format(m.from_user.mention), disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(button))

@Bot.on_chat_join_request()
async def req_accept(c, m):
    user_id = m.from_user.id
    chat_id = m.chat.id
    if not await Data.find_one({'id': user_id}):
        await Data.insert_one({'id': user_id})
    await c.approve_chat_join_request(chat_id, user_id)
    try:
        await c.send_message(user_id, ACCEPTED_TEXT.format(user=m.from_user.mention, chat=m.chat.title))
    except Exception as e:
        print(f"Error sending acceptance message to {user_id}: {e}")

# Ensure the system time is correct
print(f"System time before running bot: {datetime.datetime.now()}")

Bot.run()
