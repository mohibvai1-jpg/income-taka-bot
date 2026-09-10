import os
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# =========================
# SETTINGS
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

CHANNEL_USERNAME = "@YOUR_CHANNEL"

DB_FILE = "bot.db"

# =========================
# DATABASE
# =========================

def db():
    return sqlite3.connect(DB_FILE)

def init_db():
    con = db()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0,
            referred_by INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            method TEXT,
            number TEXT,
            status TEXT DEFAULT 'pending'
        )
    """)

    con.commit()
    con.close()


def add_user(user_id, username, referred_by=None):
    con = db()
    cur = con.cursor()

    cur.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    exists = cur.fetchone()

    if not exists:
        cur.execute(
            "INSERT INTO users (user_id, username, referred_by) VALUES (?, ?, ?)",
            (user_id, username, referred_by)
        )

    con.commit()
    con.close()


def get_balance(user_id):
    con = db()
    cur = con.cursor()

    cur.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()

    con.close()

    return row[0] if row else 0


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    referred_by = None

    # Referral link:
    # /start 123456789
    if context.args:
        try:
            referred_by = int(context.args[0])

            if referred_by == user.id:
                referred_by = None

        except ValueError:
            referred_by = None

    add_user(
        user.id,
        user.username or "",
        referred_by
    )

    keyboard = [
        [
            InlineKeyboardButton("💰 আজকের Task", callback_data="task"),
            InlineKeyboardButton("💵 Balance", callback_data="balance")
        ],
        [
            InlineKeyboardButton("👥 Referral", callback_data="referral"),
            InlineKeyboardButton("💳 Withdraw", callback_data="withdraw")
        ],
        [
            InlineKeyboardButton("📞 Support", callback_data="support"),
            InlineKeyboardButton("📢 Channel", url="https://t.me/YOUR_CHANNEL")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🤖 <b>Income Taka — Online Earning</b>\n\n"
        f"আসসালামু আলাইকুম, {user.first_name}! 👋\n\n"
        f"💰 এখানে বিভিন্ন বৈধ Task ও Reward ব্যবস্থার মাধ্যমে কাজ করা যাবে।\n\n"
        f"⚠️ কোনো OTP, Password বা ব্যক্তিগত গোপন তথ্য কাউকে দেবেন না।",
        parse_mode="HTML",
        reply_markup=reply_markup
    )


# =========================
# TASK
# =========================

async def task(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "💰 <b>আজকের Task</b>\n\n"
        "📌 বর্তমানে কোনো Task যোগ করা হয়নি।\n\n"
        "নতুন Task যোগ হলে এখানে দেখা যাবে।",
        parse_mode="HTML"
    )


# =========================
# BALANCE
# =========================

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id
    amount = get_balance(user_id)

    await update.message.reply_text(
        f"💵 <b>আপনার Balance</b>\n\n"
        f"💰 বর্তমান Balance: ৳{amount:.2f}",
        parse_mode="HTML"
    )


# =========================
# REFERRAL
# =========================

async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id
    bot_username = context.bot.username

    link = f"https://t.me/{bot_username}?start={user_id}"

    await update.message.reply_text(
        "👥 <b>Your Referral Link</b>\n\n"
        f"🔗 {link}\n\n"
        "বন্ধুদের এই লিংক শেয়ার করতে পারেন।\n"
        "Referral reward থাকলে তা আপনার Balance-এ যোগ হবে।",
        parse_mode="HTML"
    )


# =========================
# WITHDRAW
# =========================

async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "💳 <b>Withdraw</b>\n\n"
        "টাকা উত্তোলনের জন্য Support-এ যোগাযোগ করুন।\n\n"
        "📞 /support",
        parse_mode="HTML"
    )


# =========================
# HELP
# =========================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "📖 <b>Help</b>\n\n"
        "/start - 🚀 Bot চালু করুন\n"
        "/task - 💰 Task দেখুন\n"
        "/referral - 👥 Referral Link\n"
        "/balance - 💵 Balance দেখুন\n"
        "/withdraw - 💳 Withdraw\n"
        "/support - 📞 Support\n"
        "/channel - 📢 Channel",
        parse_mode="HTML"
    )


# =========================
# SUPPORT
# =========================

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "📞 <b>Support</b>\n\n"
        "কোনো সমস্যা হলে Admin-এর সাথে যোগাযোগ করুন।\n\n"
        "👉 @YOUR_ADMIN_USERNAME",
        parse_mode="HTML"
    )


# =========================
# CHANNEL
# =========================

async def channel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "📢 আমাদের Telegram Channel:\n\n"
        "👉 https://t.me/YOUR_CHANNEL"
    )


# =========================
# BUTTONS
# =========================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    if query.data == "task":

        await query.message.reply_text(
            "💰 আজকের Task\n\n"
            "বর্তমানে কোনো Task নেই।"
        )

    elif query.data == "balance":

        amount = get_balance(query.from_user.id)

        await query.message.reply_text(
            f"💵 আপনার Balance: ৳{amount:.2f}"
        )

    elif query.data == "referral":

        bot_username = context.bot.username

        link = f"https://t.me/{bot_username}?start={query.from_user.id}"

        await query.message.reply_text(
            f"👥 আপনার Referral Link:\n\n{link}"
        )

    elif query.data == "withdraw":

        await query.message.reply_text(
            "💳 Withdraw করার জন্য /withdraw লিখুন।"
        )

    elif query.data == "support":

        await query.message.reply_text(
            "📞 Support: @YOUR_ADMIN_USERNAME"
        )


# =========================
# MAIN
# =========================

def main():

    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN is not set!")
        return

    init_db()

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("task", task))
    application.add_handler(CommandHandler("referral", referral))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("withdraw", withdraw))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("support", support))
    application.add_handler(CommandHandler("channel", channel))

    application.add_handler(
        CallbackQueryHandler(button_handler)
    )

    print("Bot is running...")

    application.run_polling()


if __name__ == "__main__":
    main()
