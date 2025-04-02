# نصب پکیج‌های مورد نیاز
!pip install python-telegram-bot==13.7
!pip install pyrebase4
!pip install cryptography

import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
import pyrebase
from cryptography.fernet import Fernet
import time
import logging
import uuid
import urllib3
from requests.exceptions import RequestException

# تنظیمات اولیه
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
TOKEN = "7560347456:AAFkZR7Q8lu0NW4jBv-8sMQqQVri5H87uTA"
CHANNEL_ID = "-1002688299988"
ADMIN_ID = "6890687091"
MESSAGE_EXPIRY_SECONDS = 3 * 24 * 60 * 60
CHECK_INTERVAL_SECONDS = 3600
BOT_USERNAME = "Spank_bot_nashenasbot"

# تنظیمات Firebase
firebase_config = {
    "apiKey": "AIzaSyBR6HeWn2OgfpWnri89clifgc7sZ0_VNQk",
    "authDomain": "tel-nashenas.firebaseapp.com",
    "databaseURL": "https://tel-nashenas-default-rtdb.firebaseio.com",
    "projectId": "tel-nashenas",
    "storageBucket": "tel-nashenas.firebasestorage.app",
    "messagingSenderId": "655196052577",
    "appId": "1:655196052577:web:c66df35d53252129ea5e20"
}
firebase = pyrebase.initialize_app(firebase_config)
db = firebase.database()

# تنظیم رمزنگاری با کلید ثابت
key = b'zYqTK2g3BvcwnMyUkPQjVXiIbTwE7sNUJCx-yBejdf8='
cipher = Fernet(key)

# تابع ارسال پیام
def send_message(bot, chat_id, text, reply_markup=None, reply_to_message_id=None):
    try:
        msg = bot.send_message(chat_id=chat_id, text=text, parse_mode='Markdown', reply_markup=reply_markup, reply_to_message_id=reply_to_message_id)
        send_log_to_channel(bot, f"Message sent to {chat_id}: {text}")
        return msg
    except telegram.error.TelegramError as e:
        logging.error(f"Error sending message to {chat_id}: {e}")
        send_log_to_channel(bot, f"Error sending message to {chat_id}: {e}")
        bot.send_message(chat_id, "مشکلی پیش اومد، لطفاً دوباره امتحان کن!")
        return None

# تابع ارسال لاگ به کانال
def send_log_to_channel(bot, message):
    try:
        bot.send_message(CHANNEL_ID, f"📜 Log: {message}")
    except telegram.error.TelegramError as e:
        print(f"Failed to send log to channel: {e}")

# تنظیم logger
class TelegramLogHandler(logging.Handler):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
    def emit(self, record):
        log_entry = self.format(record)
        send_log_to_channel(self.bot, log_entry)

# تابع رمزنگاری
def encrypt_message(message):
    return cipher.encrypt(message.encode()).decode()

# تابع رمزگشایی
def decrypt_message(encrypted_message):
    return cipher.decrypt(encrypted_message.encode()).decode()

# تابع حذف پیام‌های قدیمی
def delete_old_messages(bot):
    try:
        current_time = time.time()
        messages = db.child("messages").get().val()
        if messages:
            for msg_id, msg_data in messages.items():
                if "timestamp" in msg_data and current_time - msg_data["timestamp"] > MESSAGE_EXPIRY_SECONDS:
                    db.child("messages").child(msg_id).remove()
            send_log_to_channel(bot, "Old messages deleted.")
        else:
            send_log_to_channel(bot, "No messages found to delete.")
    except Exception as e:
        logging.error(f"Error in delete_old_messages: {e}")
        send_log_to_channel(bot, f"Error in delete_old_messages: {e}")

# تولید کد رندوم
def generate_random_code(bot, chat_id):
    random_code = str(uuid.uuid4())[:8]
    db.child("users").child(chat_id).update({"anonymous_code": random_code})
    send_log_to_channel(bot, f"Generated random code {random_code} for user {chat_id}")
    return random_code

# منوها
def main_menu(chat_id):
    keyboard = [[telegram.KeyboardButton("لینک من برای دریافت پیام ناشناس 📩")],
                [telegram.KeyboardButton("تنظیمات ⚙️"), telegram.KeyboardButton("راهنما ⁉️")]]
    if str(chat_id) == ADMIN_ID:
        keyboard.append([telegram.KeyboardButton("پنل مدیریت 👨‍💼")])
    return telegram.ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def settings_menu():
    keyboard = [
        [telegram.KeyboardButton("قطع سرویس 📵"), telegram.KeyboardButton("راه اندازی سرویس 🔃")],
        [telegram.KeyboardButton("برگشت 🔙")]
    ]
    return telegram.ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def back_menu():
    keyboard = [[telegram.KeyboardButton("برگشت 🔙")]]
    return telegram.ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_menu():
    keyboard = [[telegram.KeyboardButton("آمار کاربران 📊"), telegram.KeyboardButton("بن کردن کاربر 🚫")]]
    return telegram.ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# دستور /start
def start(update, context):
    chat_id = update.message.chat_id
    first_name = update.message.from_user.first_name
    username = update.message.from_user.username or f"user_{chat_id}"
    args = context.args

    try:
        user_data = db.child("users").child(chat_id).get().val()
        # اگه کاربر ثبت‌نام نشده و کد ناشناس داره، مستقیم بره به ارسال پیام
        if not user_data and args and len(args) > 0:
            random_code = args[0]
            target = db.child("users").order_by_child("anonymous_code").equal_to(random_code).get().val()
            send_log_to_channel(context.bot, f"Checking link for {chat_id} with code {random_code}. Target data: {target}")
            if not target:
                send_message(context.bot, chat_id, "لینک نامعتبره.")
                send_log_to_channel(context.bot, f"Invalid anonymous link used by {chat_id}: {random_code}")
                return
            target_id = list(target.keys())[0]
            target_data = target[target_id]
            if not target_data.get("active", False) or target_data.get("blocked_by_admin", False):
                send_message(context.bot, chat_id, "کاربر غیرفعاله یا بن شده.")
                send_log_to_channel(context.bot, f"Target user {target_id} inactive or blocked for {chat_id}")
                return
            # ثبت‌نام سریع بدون منوی اصلی
            db.child("users").child(chat_id).set({
                "username": username,
                "active": True,
                "blocked_by_admin": False,
                "blocked_users": [],
                "anonymous_code": generate_random_code(context.bot, chat_id)
            })
            db.child("steps").child(chat_id).set({"step": "send_message", "target": target_id})
            send_message(context.bot, chat_id, "پیام ناشناست رو بنویس:", reply_markup=back_menu())
            send_log_to_channel(context.bot, f"New user {chat_id} ({username}) fast-registered and started anonymous message to {target_id}")
            return

        # ثبت‌نام عادی یا منوی اصلی
        if not user_data:
            random_code = generate_random_code(context.bot, chat_id)
            db.child("users").child(chat_id).set({
                "username": username,
                "active": True,
                "blocked_by_admin": False,
                "blocked_users": [],
                "anonymous_code": random_code
            })
            send_message(context.bot, chat_id, 
                         f"سلام {first_name} 😉\nشما در برنامه حرف به من عضو شدید. حالا می‌تونی با دریافت لینک خودت و دادن اون به دوستات، انتقادها یا حرفاشون رو ناشناس دریافت کنی!",
                         reply_markup=main_menu(chat_id))
            send_log_to_channel(context.bot, f"New user registered: {chat_id} ({username}) with code {random_code}")
        else:
            if args and len(args) > 0:
                random_code = args[0]
                target = db.child("users").order_by_child("anonymous_code").equal_to(random_code).get().val()
                send_log_to_channel(context.bot, f"Checking link for {chat_id} with code {random_code}. Target data: {target}")
                if not target:
                    send_message(context.bot, chat_id, "لینک نامعتبره.")
                    send_log_to_channel(context.bot, f"Invalid anonymous link used by {chat_id}: {random_code}")
                    return
                target_id = list(target.keys())[0]
                target_data = target[target_id]
                if not target_data.get("active", False) or target_data.get("blocked_by_admin", False):
                    send_message(context.bot, chat_id, "کاربر غیرفعاله یا بن شده.")
                    send_log_to_channel(context.bot, f"Target user {target_id} inactive or blocked for {chat_id}")
                    return
                db.child("steps").child(chat_id).set({"step": "send_message", "target": target_id})
                send_message(context.bot, chat_id, "پیام ناشناست رو بنویس:", reply_markup=back_menu())
                send_log_to_channel(context.bot, f"User {chat_id} started anonymous message to {target_id}")
            else:
                send_message(context.bot, chat_id, 
                             f"سلام {first_name} 😉\nشما در برنامه حرف به من عضو شدید. حالا می‌تونی با دریافت لینک خودت و دادن اون به دوستات، انتقادها یا حرفاشون رو ناشناس دریافت کنی!",
                             reply_markup=main_menu(chat_id))
                send_log_to_channel(context.bot, f"User {chat_id} ({username}) accessed main menu")
    except Exception as e:
        logging.error(f"Error in start: {e}")
        send_log_to_channel(context.bot, f"Error in start for {chat_id}: {e}")
        send_message(context.bot, chat_id, "مشکلی پیش اومد، لطفاً دوباره امتحان کن!")

# دستور /admin
def admin_panel(update, context):
    chat_id = update.message.chat_id
    if str(chat_id) != ADMIN_ID:
        send_message(context.bot, chat_id, "شما ادمین نیستید!")
        send_log_to_channel(context.bot, f"Non-admin {chat_id} tried to access admin panel")
        return
    send_message(context.bot, chat_id, "پنل مدیر خوش آمدید!", reply_markup=admin_menu())
    send_log_to_channel(context.bot, f"Admin {chat_id} accessed admin panel")

# دستور /ban
def ban_user(update, context):
    chat_id = update.message.chat_id
    if str(chat_id) != ADMIN_ID:
        send_message(context.bot, chat_id, "شما ادمین نیستید!")
        send_log_to_channel(context.bot, f"Non-admin {chat_id} tried to ban user")
        return
    try:
        user_id = context.args[0]
        db.child("users").child(user_id).update({"blocked_by_admin": True})
        send_message(context.bot, chat_id, f"کاربر {user_id} بن شد.")
        send_message(context.bot, user_id, "شما توسط مدیر بن شدید!")
        send_log_to_channel(context.bot, f"Admin {chat_id} banned user {user_id}")
    except IndexError:
        send_message(context.bot, chat_id, "لطفاً شناسه کاربر رو وارد کنید. مثلاً: /ban 123456789")
        send_log_to_channel(context.bot, f"Admin {chat_id} forgot to provide user ID for ban")
    except Exception as e:
        logging.error(f"Error in ban_user: {e}")
        send_log_to_channel(context.bot, f"Error in ban_user by {chat_id}: {e}")
        send_message(context.bot, chat_id, "مشکلی پیش اومد!")

# دریافت لینک ناشناس
def get_link(update, context):
    chat_id = update.message.chat_id
    user_data = db.child("users").child(chat_id).get().val()
    if not user_data:
        send_message(context.bot, chat_id, "ابتدا با /start ثبت‌نام کنید!")
        send_log_to_channel(context.bot, f"Unregistered user {chat_id} tried to get link")
        return
    random_code = user_data.get("anonymous_code")
    if not random_code:
        random_code = generate_random_code(context.bot, chat_id)
    link = f"https://t.me/{BOT_USERNAME}?start={random_code}"
    text = (f"متن زیر رو به دوستات بفرست تا برات پیام ناشناس بفرستن:\n\n"
            f"سلام، روی لینک زیر کلیک کن و هر حرفی که تو دلت هست ناشناس بفرست:\n{link}")
    send_message(context.bot, chat_id, text, reply_markup=back_menu())
    send_log_to_channel(context.bot, f"User {chat_id} generated anonymous link: {link}")

# چک کردن بلاک بودن کاربر
def check_user_blocked(chat_id, target_id):
    target_data = db.child("users").child(target_id).get().val()
    if not target_data:
        return False
    blocked_users = target_data.get("blocked_users", [])
    return str(chat_id) in blocked_users

# ارسال به کانال
def send_to_channel(bot, sender_id, target_id, text):
    try:
        bot.send_message(CHANNEL_ID, f"پیام از {sender_id} به {target_id}:\n{text}")
        send_log_to_channel(bot, f"Anonymous message from {sender_id} to {target_id}: {text}")
    except telegram.error.TelegramError as e:
        logging.error(f"Error sending to channel: {e}")
        send_log_to_channel(bot, f"Error sending anonymous message from {sender_id} to {target_id}: {e}")

# دستور /nesmsg برای نمایش پیام جدید
def show_new_message(update, context):
    chat_id = update.message.chat_id
    try:
        send_log_to_channel(context.bot, f"User {chat_id} requested new messages with /nesmsg")
        messages = db.child("messages").order_by_child("target").equal_to(str(chat_id)).get().val()
        if messages is None or not messages:
            send_log_to_channel(context.bot, f"Messages fetched for {chat_id}: None or empty - No matching messages found")
        else:
            send_log_to_channel(context.bot, f"Messages fetched for {chat_id}: {messages}")
        if not messages:
            send_message(context.bot, chat_id, "هیچ پیام ناشناسی برات نیومده!")
            return
        # پیدا کردن اولین پیام نخونده
        for msg_id, msg_data in messages.items():
            send_log_to_channel(context.bot, f"Checking message {msg_id}: {msg_data}")
            if not msg_data.get("read", False):  # اگه نخونده باشه
                try:
                    text = decrypt_message(msg_data["message"])
                except Exception as e:
                    send_log_to_channel(context.bot, f"Decryption failed for message {msg_id}: {e}")
                    continue
                keyboard = [
                    [telegram.InlineKeyboardButton("ریپلای", callback_data=f"reply_{msg_id}"),
                     telegram.InlineKeyboardButton("بلاک", callback_data=f"block_{msg_id}"),
                     telegram.InlineKeyboardButton("گزارش", callback_data=f"report_{msg_id}")]
                ]
                reply_markup = telegram.InlineKeyboardMarkup(keyboard)
                send_message(context.bot, chat_id, f"پیام ناشناس:\n{text}", reply_markup=reply_markup)
                db.child("messages").child(msg_id).update({"read": True})
                send_log_to_channel(context.bot, f"User {chat_id} read message {msg_id}")
                return
        send_message(context.bot, chat_id, "پیام ناشناس جدیدی نداری!")
    except Exception as e:
        logging.error(f"Error in show_new_message: {e}")
        send_log_to_channel(context.bot, f"Error in show_new_message for {chat_id}: {e}")
        send_message(context.bot, chat_id, "مشکلی پیش اومد، لطفاً دوباره امتحان کن!")

# مدیریت کلیک روی دکمه‌ها
def handle_button(update, context):
    query = update.callback_query
    chat_id = query.message.chat_id
    data = query.data
    msg_id = data.split("_")[1]

    try:
        send_log_to_channel(context.bot, f"User {chat_id} clicked button: {data}")
        msg_data = db.child("messages").child(msg_id).get().val()
        send_log_to_channel(context.bot, f"Message data for {msg_id}: {msg_data}")
        if not msg_data:
            query.edit_message_text("این پیام دیگه وجود نداره!")
            send_log_to_channel(context.bot, f"Message {msg_id} not found in database for {chat_id}")
            return
        sender_id = msg_data["sender"]

        if data.startswith("reply_"):
            db.child("steps").child(chat_id).set({"step": "reply_message", "target": sender_id, "original_msg_id": msg_id})
            query.edit_message_text("جوابت رو بنویس:")
            send_log_to_channel(context.bot, f"User {chat_id} started reply to {sender_id} for message {msg_id}")
        
        elif data.startswith("block_"):
            user_data = db.child("users").child(chat_id).get().val()
            blocked_users = user_data.get("blocked_users", [])
            if str(sender_id) not in blocked_users:
                blocked_users.append(str(sender_id))
                db.child("users").child(chat_id).update({"blocked_users": blocked_users})
                query.edit_message_text("فرستنده این پیام بلاک شد!")
                send_log_to_channel(context.bot, f"User {chat_id} blocked {sender_id}")
            else:
                query.edit_message_text("این کاربر قبلاً بلاک شده!")
        
        elif data.startswith("report_"):
            reports = msg_data.get("reports", 0) + 1
            db.child("messages").child(msg_id).update({"reports": reports})
            if reports >= 6:
                context.bot.send_message(ADMIN_ID, 
                                       f"کاربر {sender_id} بیش از 6 بار گزارش شده. پیام:\n{decrypt_message(msg_data['message'])}\nبرای بن کردن، دستور /ban {sender_id} رو بفرست.")
                send_log_to_channel(context.bot, f"User {sender_id} reported 6+ times by {chat_id}")
            query.edit_message_text("پیام گزارش شد!")
            send_log_to_channel(context.bot, f"Message {msg_id} reported by {chat_id}")
        
    except Exception as e:
        logging.error(f"Error in handle_button: {e}")
        send_log_to_channel(context.bot, f"Error in handle_button for {chat_id}: {e}")
        query.edit_message_text("مشکلی پیش اومد!")

# مدیریت پیام‌های متنی (دکمه‌ها و پیام ناشناس)
def handle_text(update, context):
    if not update.message or not hasattr(update.message, 'chat_id') or update.message.chat.type == 'channel':
        return
    chat_id = update.message.chat_id
    text = update.message.text

    # چک کردن حالت ریپلای
    steps = db.child("steps").child(chat_id).get().val()
    if steps and steps.get("step") == "reply_message":
        target_id = steps["target"]
        original_msg_id = steps["original_msg_id"]
        if check_user_blocked(chat_id, target_id):
            send_message(context.bot, chat_id, "این کاربر شما رو بلاک کرده.")
            send_log_to_channel(context.bot, f"User {chat_id} blocked by target {target_id}")
            return
        encrypted_reply = encrypt_message(text)
        reply_msg_id = db.child("messages").push({
            "sender": chat_id,
            "target": target_id,
            "message": encrypted_reply,
            "timestamp": time.time(),
            "reports": 0,
            "reply_to": original_msg_id,
            "read": False
        })["name"]
        send_to_channel(context.bot, chat_id, target_id, text)
        send_message(context.bot, target_id, "پیام ناشناس جدید داری! برای خوندن /nesmsg رو بزن")
        send_message(context.bot, chat_id, "پاسخت با موفقیت ارسال شد!")
        db.child("steps").child(chat_id).remove()
        send_log_to_channel(context.bot, f"Reply sent from {chat_id} to {target_id} for message {original_msg_id} with msg_id {reply_msg_id}")
        return

    # مدیریت دکمه‌ها
    if text == "لینک من برای دریافت پیام ناشناس 📩":
        get_link(update, context)
    elif text == "تنظیمات ⚙️":
        send_message(context.bot, chat_id, "تنظیمات:", reply_markup=settings_menu())
        send_log_to_channel(context.bot, f"User {chat_id} accessed settings")
    elif text == "راهنما ⁉️":
        send_message(context.bot, chat_id, "راهنما:\n- برای دریافت لینک از دکمه مربوطه استفاده کن.\n- برای ارسال پیام ناشناس، لینک رو باز کن و پیامت رو بنویس.\n- برای دیدن پیام‌ها، /nesmsg رو بزن.")
        send_log_to_channel(context.bot, f"User {chat_id} accessed help")
    elif text == "قطع سرویس 📵":
        db.child("users").child(chat_id).update({"active": False})
        send_message(context.bot, chat_id, "سرویس شما غیرفعال شد.", reply_markup=main_menu(chat_id))
        send_log_to_channel(context.bot, f"User {chat_id} disabled service")
    elif text == "راه اندازی سرویس 🔃":
        db.child("users").child(chat_id).update({"active": True})
        send_message(context.bot, chat_id, "سرویس شما فعال شد.", reply_markup=main_menu(chat_id))
        send_log_to_channel(context.bot, f"User {chat_id} enabled service")
    elif text == "برگشت 🔙":
        send_message(context.bot, chat_id, "بازگشت به منوی اصلی", reply_markup=main_menu(chat_id))
        send_log_to_channel(context.bot, f"User {chat_id} returned to main menu")
    elif text == "پنل مدیریت 👨‍💼" and str(chat_id) == ADMIN_ID:
        send_message(context.bot, chat_id, "پنل مدیر خوش آمدید!", reply_markup=admin_menu())
        send_log_to_channel(context.bot, f"Admin {chat_id} accessed admin panel")
    elif text == "آمار کاربران 📊" and str(chat_id) == ADMIN_ID:
        users = db.child("users").get().val()
        total = len(users) if users else 0
        send_message(context.bot, chat_id, f"تعداد کاربران: {total}")
        send_log_to_channel(context.bot, f"Admin {chat_id} checked user stats: {total} users")
    elif text == "بن کردن کاربر 🚫" and str(chat_id) == ADMIN_ID:
        send_message(context.bot, chat_id, "شناسه کاربر رو با دستور /ban بفرستید. مثلاً: /ban 123456789")
        send_log_to_channel(context.bot, f"Admin {chat_id} requested ban instructions")
    else:
        # ارسال پیام ناشناس
        try:
            user_data = db.child("users").child(chat_id).get().val()
            if not user_data:
                send_message(context.bot, chat_id, "ابتدا با /start ثبت‌نام کنید!")
                send_log_to_channel(context.bot, f"Unregistered user {chat_id} tried to send message")
                return
            if user_data.get("blocked_by_admin", False):
                send_message(context.bot, chat_id, "شما توسط مدیر بن شدید.")
                send_log_to_channel(context.bot, f"Blocked user {chat_id} tried to send message")
                return
            
            steps = db.child("steps").child(chat_id).get().val()
            if steps and steps["step"] == "send_message":
                target_id = steps["target"]
                if check_user_blocked(chat_id, target_id):
                    send_message(context.bot, chat_id, "این کاربر شما رو بلاک کرده.")
                    send_log_to_channel(context.bot, f"User {chat_id} blocked by target {target_id}")
                    return
                encrypted_msg = encrypt_message(text)
                msg_id = db.child("messages").push({
                    "sender": chat_id,
                    "target": target_id,
                    "message": encrypted_msg,
                    "timestamp": time.time(),
                    "reports": 0,
                    "read": False
                })["name"]
                send_to_channel(context.bot, chat_id, target_id, text)
                send_message(context.bot, target_id, "پیام ناشناس جدید داری! برای خوندن /nesmsg رو بزن")
                send_message(context.bot, chat_id, "پیامت با موفقیت رفت!")
                db.child("steps").child(chat_id).remove()
                send_log_to_channel(context.bot, f"Anonymous message sent from {chat_id} to {target_id} with msg_id {msg_id}")
        except Exception as e:
            logging.error(f"Error in handle_text (send_anonymous): {e}")
            send_log_to_channel(context.bot, f"Error in sending anonymous message by {chat_id}: {e}")
            send_message(context.bot, chat_id, "مشکلی پیش اومد، لطفاً دوباره امتحان کن!")

# تنظیمات ربات و حلقه اصلی
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    log_handler = TelegramLogHandler(updater.bot)
    log_handler.setLevel(logging.INFO)
    logging.getLogger().addHandler(log_handler)

    # هندلر خطاها
    def error_handler(update, context):
        if isinstance(context.error, telegram.error.Conflict):
            logging.error("Conflict detected: Another instance is running. Stopping this instance.")
            send_log_to_channel(updater.bot, "Conflict detected: Another instance running. Stopping.")
            updater.stop()
        elif isinstance(context.error, (urllib3.exceptions.HTTPError, RequestException)):
            logging.error(f"Network error detected: {context.error}. Retrying in 5 seconds...")
            send_log_to_channel(updater.bot, f"Network error: {context.error}. Retrying in 5s...")
            time.sleep(5)
            updater.start_polling()
        else:
            logging.error(f"Unhandled error: {context.error}", exc_info=True)
            send_log_to_channel(updater.bot, f"Unhandled error: {context.error}")

    dp.add_error_handler(error_handler)

    # هندلرها
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("admin", admin_panel))
    dp.add_handler(CommandHandler("ban", ban_user))
    dp.add_handler(CommandHandler("nesmsg", show_new_message))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command & ~Filters.chat_type.channel, handle_text))
    dp.add_handler(CallbackQueryHandler(handle_button))

    # شروع ربات
    max_retries = 3
    for attempt in range(max_retries):
        try:
            updater.start_polling()
            send_log_to_channel(updater.bot, "Bot started polling.")
            break
        except (telegram.error.NetworkError, urllib3.exceptions.HTTPError, RequestException) as e:
            logging.error(f"Failed to start polling (attempt {attempt + 1}/{max_retries}): {e}")
            send_log_to_channel(updater.bot, f"Failed to start due to network error: {e}. Retrying in 5s...")
            time.sleep(5)
    else:
        send_log_to_channel(updater.bot, "Failed to start bot after maximum retries. Exiting.")
        return

    # حلقه برای حذف پیام‌های قدیمی
    while True:
        delete_old_messages(updater.bot)
        time.sleep(CHECK_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
