import telebot
import os
import sqlite3
import subprocess
import time

dir = "/path/to/dir"
bot_token = "your_bot_token"
channel_id = "your_channel_id"

bot = telebot.TeleBot(bot_token, parse_mode=None)
os.makedirs(dir) if not os.path.exists(dir) else None

db_path = f"{dir}/v2vn.db"
if not os.path.exists(db_path):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE users (\
            id INTEGER PRIMARY KEY, \
            user_id TEXT, \
            full_name TEXT, \
            username TEXT, \
            count TEXT, \
            timestamp INTEGER \
            )')
        cursor.execute('CREATE TABLE files (\
            id INTEGER PRIMARY KEY, \
            user_id TEXT, \
            file_id TEXT, \
            timestamp INTEGER \
            )')
        conn.commit()

def cropvideo(new_path, user_id):
    timestamp = time.time()
    out_path = f"{dir}/{user_id}/output_{timestamp}.mp4"
    ffmpeg_cmd = [
        "ffmpeg",
        "-i", new_path,
        "-t", "59",
        "-c:a", "aac",
        "-c:v", "libx264",
        "-filter:v", "crop=min(iw\,ih):min(iw\,ih),scale=512:-1, crop=512:512",
        "-crf", "26",
        "-y", out_path
    ]
    subprocess.run(ffmpeg_cmd)
    return out_path

def getuser(message):
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    fullname = f"{first_name} {last_name}" if last_name else first_name
    username = message.from_user.username
    user_id = message.from_user.id
    player = f"{fullname} @{username}({user_id})" if username else f"{fullname}({user_id})"
    return player

def logging(event):
    now = time.time()
    local_time = time.localtime(now)
    date_str = time.strftime("%Y-%m-%d %H:%M:%S", local_time)

    event = f"[{date_str}] {event}\n"
    log_file = f"{dir}/vnotebot.log"
    with open(log_file, "a") as f:
        f.write(event)
    print(f"{event}")

def adduser(message):
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    fullname = f"{first_name} {last_name}" if last_name else first_name
    username = message.from_user.username
    user_id = message.from_user.id
    timestamp = message.date

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT count(user_id) FROM users WHERE user_id=?',(user_id,))
        record = cursor.fetchone()[0]
        user_exists = True if record > 0 else False

    if not user_exists:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO users \
                (user_id, full_name, username, timestamp, count) \
                VALUES (?, ?, ?, ?, 0)',(user_id, fullname, username, timestamp))
        conn.commit()

        player = getuser(message)
        logging(f"{player} Registered.")

@bot.message_handler(content_types=["video"])
def handle_video(message):
    if message.chat.type == "private":
        user_id = message.from_user.id

        adduser(message)

        file_size = message.video.file_size
        if file_size < 20971520:
            editlater = bot.send_message(user_id, "Downloading...").message_id
            video_fid = message.video.file_id
            file_info = bot.get_file(video_fid)

            download_file = bot.download_file(file_info.file_path)
            os.makedirs(f"{dir}/{user_id}/videos", exist_ok=True)
            path = f"{dir}/{user_id}/{file_info.file_path}"
            with open(path, "wb") as f:
                f.write(download_file)
            new_fname = message.video.file_name
            new_path = f"{dir}/{user_id}/{message.date}_{new_fname}"
            os.rename(path, new_path)

            try:
                editlater = bot.edit_message_text("Cropping video...", user_id, editlater).message_id
            except:
                pass

            send_video = cropvideo(new_path, user_id)

            try:
                editlater = bot.edit_message_text("Sending back...", user_id, editlater).message_id
            except:
                pass

            with open(send_video, "rb") as vf:
                video_fid = bot.send_video_note(user_id, vf, reply_to_message_id=message.id, allow_sending_without_reply=True).video_note.file_id
                bot.send_video_note(channel_id, video_fid)
            os.remove(send_video)

            try:
                bot.delete_message(user_id, editlater)
            except:
                pass

            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE users SET count=COALESCE(count, 0) + 1 \
                    WHERE user_id=?',(user_id,))
                timestamp = message.date
                cursor.execute('INSERT INTO files (user_id, file_id, timestamp) VALUES (?, ?, ?)', \
                    (user_id, video_fid, timestamp))
                conn.commit()
            player = getuser(message)
            logging(f"{player} Made a video_note.")
        else:
            bot.send_message(user_id, "File too big. Send video smaller than 20M.")

            player = getuser(message)
            logging(f"{player} Send a file bigger than 20MB.")

@bot.message_handler(commands=["start"])
def handle_start(message):
    bot.send_message(message.from_user.id, "Just send me video!")
    adduser(message)

bot.infinity_polling(timeout=10, long_polling_timeout=5)
