# main.py
from flask import Flask, request
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Bot
import requests
from bs4 import BeautifulSoup
import os
import subprocess
import telegram

app = Flask(__name__)

# گرفتن توکن از متغیر محیطی
TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    raise ValueError("توکن ربات توی متغیرهای محیطی پیدا نشد! لطفاً TOKEN رو توی Railway تنظیم کن.")
bot = Bot(TOKEN)

# متغیرها برای ذخیره ویدیوها
video_links = []
selected_videos = {}

@app.route('/')
def hello():
    return "ربات فعاله!"

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    dp.process_update(update)
    return 'OK'

def start(update, context):
    update.message.reply_text("سلام! یه لینک صفحه وب بفرست تا ویدیوها رو لیست کنم.")

def handle_url(update, context):
    url = update.message.text
    if not url.startswith("http"):
        update.message.reply_text("لطفاً یه لینک معتبر بفرست!")
        return
    
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        video_tags = soup.find_all('video') + soup.find_all('source')
        global video_links
        video_links = [tag.get('src') for tag in video_tags if tag.get('src') and tag.get('src').startswith('http')]
        
        if not video_links:
            update.message.reply_text("ویدیویی توی این صفحه پیدا نشد!")
            return
        
        keyboard = []
        for i, link in enumerate(video_links):
            keyboard.append([InlineKeyboardButton(f"ویدیو {i+1}", callback_data=f"vid_{i}")])
        keyboard.append([InlineKeyboardButton("دانلود انتخاب‌شده‌ها", callback_data="download")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("ویدیوها رو انتخاب کن:", reply_markup=reply_markup)
        selected_videos[update.message.chat_id] = set()
        
    except Exception as e:
        update.message.reply_text(f"خطا در گرفتن صفحه: {str(e)}")

def button_handler(update, context):
    query = update.callback_query
    query.answer()
    chat_id = query.message.chat_id
    
    if query.data == "download":
        if not selected_videos.get(chat_id):
            query.edit_message_text("هیچ ویدیویی انتخاب نشده!")
            return
        
        query.edit_message_text("در حال دانلود و تبدیل ویدیوها... صبر کن!")
        for vid_index in selected_videos[chat_id]:
            link = video_links[vid_index]
            download_and_convert(query, context, link, chat_id)
        query.edit_message_text("دانلود و تبدیل تموم شد!")
        selected_videos[chat_id].clear()
        return
    
    vid_index = int(query.data.split("_")[1])
    if vid_index in selected_videos[chat_id]:
        selected_videos[chat_id].remove(vid_index)
        query.edit_message_text(f"ویدیو {vid_index+1} از انتخاب حذف شد.")
    else:
        selected_videos[chat_id].add(vid_index)
        query.edit_message_text(f"ویدیو {vid_index+1} انتخاب شد.")
    
    keyboard = []
    for i, link in enumerate(video_links):
        label = f"ویدیو {i+1} {'✅' if i in selected_videos[chat_id] else ''}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"vid_{i}")])
    keyboard.append([InlineKeyboardButton("دانلود انتخاب‌شده‌ها", callback_data="download")])
    query.edit_message_reply_markup(InlineKeyboardMarkup(keyboard))

def download_and_convert(query, context, video_url, chat_id):
    try:
        response = requests.get(video_url, stream=True)
        input_file = "input_video.temp"
        with open(input_file, 'wb') as f:
            f.write(response.content)
        
        file_size_mb = os.path.getsize(input_file) / (1024 * 1024)
        if file_size_mb > 50:
            query.message.reply_text(f"ویدیو با حجم {file_size_mb:.2f} مگابایت بزرگ‌تر از 50 مگابایته!")
            os.remove(input_file)
            return
        
        output_file = "output_video.mp4"
        subprocess.run([
            "ffmpeg", "-y",
            "-i", input_file,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-b:v", "2M",
            output_file
        ], capture_output=True, text=True, check=True)
        
        with open(output_file, "rb") as f:
            context.bot.send_video(chat_id=chat_id, video=f)
        
        os.remove(input_file)
        os.remove(output_file)
        
    except Exception as e:
        query.message.reply_text(f"خطا در دانلود یا تبدیل: {str(e)}")

# تنظیم Dispatcher
dp = Dispatcher(bot, None, workers=0)
dp.add_handler(CommandHandler("start", start))
dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_url))
dp.add_handler(CallbackQueryHandler(button_handler))

if __name__ == "__main__":
    # گرفتن پورت از متغیر محیطی Railway
    PORT = int(os.environ.get("PORT", 5000))
    # تنظیم Webhook با دامنه Railway
    RAILWAY_URL = os.environ.get("RAILWAY_URL", f"https://your-railway-app.railway.app")
    bot.setWebhook(f"{RAILWAY_URL}/{TOKEN}")
    app.run(host="0.0.0.0", port=PORT)
