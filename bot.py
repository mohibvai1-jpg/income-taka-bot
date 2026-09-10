import os
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# =========================================================
# SETTINGS
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = os.environ.get("ADMIN_ID")

CHANNEL_USERNAME = "@YOUR_CHANNEL"
CHANNEL_URL = "https://t.me/YOUR_CHANNEL"
SUPPORT_USERNAME = "@YOUR_ADMIN_USERNAME"

DB_FILE = "bot.db"


# =========================================================
# CHECK ENVIRONMENT VARIABLES
# =========================================================

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing!")

if not ADMIN_ID:
    raise RuntimeError("ADMIN_ID environment variable is missing!")


# =========================================================
# DATABASE
# =========================================================

def init_db():
    conn = sqlite3.connect(DB_FILE)

    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance REAL DEFAULT 0,
            referrals INTEGER DEFAULT 0,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def add_user(user):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO users
        (user_id, username, first_name)
        VALUES (?, ?, ?)
    """, (
        user.id,
        user.username or "",
        user.first_name or ""
    ))

    conn.commit()
    conn.close()


def get_balance(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT balance FROM users WHERE user_id = ?",
        (user_id,)
    )

    result = cursor.fetchone()

    conn.close()

    if result:
        return result[0]

    return 0


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    add_user(user)

    keyboard = [
        [
            InlineKeyboardButton(
                "💰 আজকের Task",
                callback_data="task"
            )
        ],
        [
            InlineKeyboardButton(
                "👥 Referral",
                callback_data="referral"
            ),
            InlineKeyboardButton(
                "💵 Balance",
                callback_data="balance"
            )
        ],
        [
            InlineKeyboardButton(
                "💳 Withdraw",
                callback_data="withdraw"
            )
        ],
        [
            InlineKeyboardButton(
                "📢 আমাদের Channel",
                url=CHANNEL_URL
            )
        ],
        [
            InlineKeyboardButton(
                "📞 Support",
                url=f"https://t.me/{SUPPORT_USERNAME.replace('@', '')}"
            )
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    text = f"""
🤖 *Income Taka — Online Earning*

আসসালামু আলাইকুম, {user.first_name}! 👋

💰 এখানে বিভিন্ন বৈধ Task ও Earning Opportunity সম্পর্কে জানতে পারবেন।

🎁 Daily Task
👥 Referral
💵 Balance
💳 Withdraw

⚠️ কোনো OTP, Password বা ব্যক্তিগত গোপন তথ্য কাউকে দেবেন না।

নিচের Menu থেকে একটি অপশন নির্বাচন করুন 👇
"""

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


# =========================================================
# TASK
# =========================================================

async def task(update: Update, context: ContextTypes.DEFAULT_TYPE):

    add_user(update.effective_user)

    text = """
💰 *আজকের Task*

আজকের Task এখনো যোগ করা হয়নি।

📌 Admin নতুন Task যোগ করলে এখানে দেখানো হবে।

⚠️ কোনো Task-এর জন্য আগে টাকা পাঠানোর প্রয়োজন হলে সতর্ক থাকুন।
"""

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# =========================================================
# REFERRAL
# =========================================================

async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    add_user(user)

    bot_username = context.bot.username

    referral_link = f"https://t.me/{bot_username}?start=ref_{user.id}"

    text = f"""
👥 *আপনার Referral*

আপনার Referral Link:

`{referral_link}`

বন্ধুদের এই লিংকটি শেয়ার করতে পারেন।

🎁 Referral Reward-এর নিয়ম Admin ঘোষণা করবে।
"""

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# =========================================================
# BALANCE
# =========================================================

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    add_user(user)

    user_balance = get_balance(user.id)

    text = f"""
💵 *আপনার Balance*

বর্তমান Balance:
💰 *৳{user_balance:.2f}*

আরও বৈধ Task সম্পন্ন করে আয় করতে পারেন।
"""

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# =========================================================
# WITHDRAW
# =========================================================

async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = """
💳 *Withdraw*

টাকা তোলার নিয়ম:

1️⃣ আপনার Balance দেখুন
2️⃣ Withdraw-এর ন্যূনতম সীমা পূরণ করুন
3️⃣ Admin-এর নির্দেশনা অনুসরণ করুন

📞 Withdraw সংক্রান্ত সাহায্যের জন্য Support-এ যোগাযোগ করুন।

⚠️ Withdraw করার জন্য কাউকে OTP বা Password দেবেন না।
"""

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# =========================================================
# HELP
# =========================================================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = """
📖 *Help*

/start - 🚀 Bot চালু করুন
/task - 💰 আজকের Task দেখুন
/referral - 👥 Referral Link দেখুন
/balance - 💵 আপনার Balance দেখুন
/withdraw - 💳 টাকা তোলার নিয়ম
/help - 📖 সাহায্য
/support - 📞 Support
/channel - 📢 আমাদের Channel

যেকোনো সমস্যা হলে Support-এ যোগাযোগ করুন।
"""

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# =========================================================
# SUPPORT
# =========================================================

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = f"""
📞 *Support*

সাহায্যের জন্য আমাদের Admin-এর সাথে যোগাযোগ করুন:

{SUPPORT_USERNAME}

⚠️ আপনার Bot Token, OTP বা Password কাউকে দেবেন না।
"""

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# =========================================================
# CHANNEL
# =========================================================

async def channel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [
            InlineKeyboardButton(
                "📢 Channel Join করুন",
                url=CHANNEL_URL
            )
        ]
    ]

    await update.message.reply_text(
        "📢 আমাদের Channel:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================================================
# BUTTON HANDLER
# =========================================================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    user = query.from_user

    add_user(user)

    if query.data == "task":

        await query.message.reply_text(
            "💰 আজকের Task এখনো যোগ করা হয়নি।"
        )

    elif query.data == "referral":

        bot_username = context.bot.username

        referral_link = (
            f"https://t.me/{bot_username}?start=ref_{user.id}"
        )

        await query.message.reply_text(
            f"👥 আপনার Referral Link:\n\n{referral_link}"
        )

    elif query.data == "balance":

        user_balance = get_balance(user.id)

        await query.message.reply_text(
            f"💵 আপনার Balance: ৳{user_balance:.2f}"
        )

    elif query.data == "withdraw":

        await query.message.reply_text(
            "💳 Withdraw-এর নিয়ম জানতে /withdraw ব্যবহার করুন।"
        )


# =========================================================
# RENDER HEALTH SERVER
# =========================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        self.send_response(200)

        self.send_header(
            "Content-type",
            "text/plain"
        )

        self.end_headers()

        self.wfile.write(
            b"Income Taka Bot is running!"
        )

    def log_message(self, format, *args):
        return


def start_health_server():

    port = int(
        os.environ.get("PORT", "10000")
    )

    server = HTTPServer(
        ("0.0.0.0", port),
        HealthHandler
    )

    print(f"Health server running on port {port}")

    server.serve_forever()


# =========================================================
# MAIN
# =========================================================

def main():

    print("Starting Income Taka Bot...")

    init_db()

    # Start Render HTTP server
    health_thread = threading.Thread(
        target=start_health_server,
        daemon=True
    )

    health_thread.start()

    # Create Telegram application
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Commands
    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("task", task)
    )

    application.add_handler(
        CommandHandler("referral", referral)
    )

    application.add_handler(
        CommandHandler("balance", balance)
    )

    application.add_handler(
        CommandHandler("withdraw", withdraw)
    )

    application.add_handler(
        CommandHandler("help", help_command)
    )

    application.add_handler(
        CommandHandler("support", support)
    )

    application.add_handler(
        CommandHandler("channel", channel)
    )

    # Buttons
    from telegram.ext import CallbackQueryHandler

    application.add_handler(
        CallbackQueryHandler(button_handler)
    )

    print("Bot is running!")

    application.run_polling()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    main()
