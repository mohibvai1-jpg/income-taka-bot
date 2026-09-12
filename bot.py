import os
import sqlite3
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


# =========================================================
# SETTINGS
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

# এগুলো পরে নিজের তথ্য দিয়ে পরিবর্তন করবেন
CHANNEL_URL = "https://t.me/YOUR_CHANNEL"
SUPPORT_USERNAME = "@YOUR_ADMIN_USERNAME"

DB_FILE = "bot.db"


# =========================================================
# HEALTH SERVER FOR RENDER
# =========================================================

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Income Taka Bot is running!")

    def log_message(self, format, *args):
        return


def run_health_server():
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()


# =========================================================
# DATABASE
# =========================================================

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance REAL DEFAULT 0,
            referred_by INTEGER DEFAULT NULL,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            reward REAL DEFAULT 0,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            user_id INTEGER,
            proof TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            method TEXT,
            number TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


# =========================================================
# USER FUNCTIONS
# =========================================================

def add_user(user, referred_by=None):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT user_id FROM users WHERE user_id = ?",
        (user.id,)
    )

    exists = cur.fetchone()

    if not exists:
        cur.execute("""
            INSERT INTO users
            (user_id, username, first_name, balance, referred_by, created_at)
            VALUES (?, ?, ?, 0, ?, ?)
        """, (
            user.id,
            user.username or "",
            user.first_name or "",
            referred_by,
            datetime.now().isoformat()
        ))

        conn.commit()

    conn.close()


def get_balance(user_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT balance FROM users WHERE user_id = ?",
        (user_id,)
    )

    row = cur.fetchone()
    conn.close()

    if row:
        return float(row["balance"])

    return 0.0


def change_balance(user_id, amount):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET balance = balance + ?
        WHERE user_id = ?
    """, (amount, user_id))

    conn.commit()
    conn.close()


def is_admin(user_id):
    return user_id == ADMIN_ID


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    referred_by = None

    # Referral link: /start 123456
    if context.args:
        try:
            referred_by = int(context.args[0])

            if referred_by == user.id:
                referred_by = None

        except ValueError:
            referred_by = None

    add_user(user, referred_by)

    keyboard = [
        [
            InlineKeyboardButton(
                "💰 আজকের Task",
                callback_data="tasks"
            ),
            InlineKeyboardButton(
                "💵 Balance",
                callback_data="balance"
            )
        ],
        [
            InlineKeyboardButton(
                "👥 Referral",
                callback_data="referral"
            ),
            InlineKeyboardButton(
                "💳 Withdraw",
                callback_data="withdraw"
            )
        ],
        [
            InlineKeyboardButton(
                "📖 Help",
                callback_data="help"
            ),
            InlineKeyboardButton(
                "📞 Support",
                callback_data="support"
            )
        ],
        [
            InlineKeyboardButton(
                "📢 Channel",
                url=CHANNEL_URL
            )
        ]
    ]

    text = (
        "🤖 <b>Income Taka — Online Earning</b>\n\n"
        f"👋 আসসালামু আলাইকুম {user.first_name}!\n\n"
        "📱 বিভিন্ন Task সম্পন্ন করে Earning করতে পারবেন।\n"
        "🎁 Daily Task\n"
        "👥 Referral\n"
        "💰 Balance\n"
        "💳 Withdrawal\n\n"
        "⚠️ কোনো OTP বা Password কারো সাথে শেয়ার করবেন না।"
    )

    await update.effective_message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================================================
# TASK LIST
# =========================================================

async def tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT * FROM tasks
        ORDER BY id DESC
    """)

    rows = cur.fetchall()
    conn.close()

    if not rows:
        await message.reply_text(
            "📭 বর্তমানে কোনো Task নেই।\n\n"
            "পরে আবার চেষ্টা করুন।"
        )
        return

    keyboard = []

    for row in rows:
        keyboard.append([
            InlineKeyboardButton(
                f"💰 {row['title']} — ৳{row['reward']}",
                callback_data=f"do:{row['id']}"
            )
        ])

    await message.reply_text(
        "💰 <b>Available Tasks</b>\n\n"
        "নিচের Task থেকে একটি নির্বাচন করুন:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================================================
# TASK DETAIL + PROOF
# =========================================================

SUBMIT_PROOF = 1


async def do_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query

    await q.answer()

    try:
        task_id = int(q.data.split(":")[1])
    except Exception:
        await q.message.reply_text("❌ Task ID সঠিক নয়।")
        return ConversationHandler.END

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    )

    task = cur.fetchone()
    conn.close()

    if not task:
        await q.message.reply_text(
            "❌ এই Task আর পাওয়া যাচ্ছে না।"
        )
        return ConversationHandler.END

    context.user_data["task_id"] = task_id

    text = (
        f"📌 <b>{task['title']}</b>\n\n"
        f"📝 <b>Task:</b>\n{task['description']}\n\n"
        f"💰 <b>Reward:</b> ৳{task['reward']}\n\n"
        "✅ Task সম্পন্ন করার পর Screenshot/Proof-এর তথ্য "
        "এই চ্যাটে পাঠান।\n\n"
        "❌ বাতিল করতে /cancel লিখুন।"
    )

    await q.message.reply_text(
        text,
        parse_mode="HTML"
    )

    return SUBMIT_PROOF


async def submit_proof(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user = update.effective_user
    proof = update.effective_message.text

    task_id = context.user_data.get("task_id")

    if not task_id:
        await update.effective_message.reply_text(
            "❌ Task পাওয়া যায়নি। আবার /task দিয়ে চেষ্টা করুন।"
        )
        return ConversationHandler.END

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    )

    task = cur.fetchone()

    if not task:
        conn.close()

        await update.effective_message.reply_text(
            "❌ এই Task আর পাওয়া যাচ্ছে না।"
        )

        return ConversationHandler.END

    # Same user + same task pending submission check
    cur.execute("""
        SELECT id FROM submissions
        WHERE task_id = ?
        AND user_id = ?
        AND status = 'pending'
    """, (task_id, user.id))

    existing = cur.fetchone()

    if existing:
        conn.close()

        await update.effective_message.reply_text(
            "⏳ আপনার এই Task-এর Proof ইতোমধ্যে জমা আছে।\n"
            "Admin review করার জন্য অপেক্ষা করুন।"
        )

        return ConversationHandler.END

    # এখানে 4টি placeholder
    cur.execute("""
        INSERT INTO submissions
        (task_id, user_id, proof, status)
        VALUES (?, ?, ?, 'pending')
    """, (
        task_id,
        user.id,
        proof
    ))

    conn.commit()
    submission_id = cur.lastrowid
    conn.close()

    await update.effective_message.reply_text(
        "✅ <b>Proof সফলভাবে জমা হয়েছে!</b>\n\n"
        f"🆔 Submission ID: {submission_id}\n"
        "⏳ Admin আপনার Proof যাচাই করবেন।\n"
        "Approved হলে Reward Balance-এ যোগ হবে।",
        parse_mode="HTML"
    )

    # Notify admin
    if ADMIN_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    "🔔 <b>New Task Submission</b>\n\n"
                    f"👤 User ID: {user.id}\n"
                    f"👤 Username: @{user.username or 'N/A'}\n"
                    f"📌 Task ID: {task_id}\n"
                    f"🆔 Submission ID: {submission_id}\n\n"
                    f"📄 Proof:\n{proof}"
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass

    context.user_data.pop("task_id", None)

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("task_id", None)

    await update.effective_message.reply_text(
        "❌ কাজ বাতিল করা হয়েছে।"
    )

    return ConversationHandler.END


# =========================================================
# BALANCE
# =========================================================

async def show_balance(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user = update.effective_user
    balance_amount = get_balance(user.id)

    await update.effective_message.reply_text(
        "💵 <b>Your Balance</b>\n\n"
        f"💰 Balance: ৳{balance_amount:.2f}",
        parse_mode="HTML"
    )


# =========================================================
# REFERRAL
# =========================================================

async def referral(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user = update.effective_user

    bot = await context.bot.get_me()

    referral_link = (
        f"https://t.me/{bot.username}?start={user.id}"
    )

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) AS total FROM users WHERE referred_by = ?",
        (user.id,)
    )

    row = cur.fetchone()
    conn.close()

    total_referrals = row["total"] if row else 0

    text = (
        "👥 <b>Referral System</b>\n\n"
        f"🔗 আপনার Referral Link:\n"
        f"<code>{referral_link}</code>\n\n"
        f"👤 Total Referral: {total_referrals}\n\n"
        "বন্ধুদের এই Link দিয়ে Bot-এ Join করাতে পারেন।"
    )

    await update.effective_message.reply_text(
        text,
        parse_mode="HTML"
    )


# =========================================================
# WITHDRAW
# =========================================================

WITHDRAW_AMOUNT = 1
WITHDRAW_METHOD = 2
WITHDRAW_NUMBER = 3


async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    balance_amount = get_balance(user.id)

    if balance_amount <= 0:
        await update.effective_message.reply_text(
            "💳 আপনার Balance বর্তমানে ৳0.00\n\n"
            "আগে Task সম্পন্ন করে Balance তৈরি করুন।"
        )
        return ConversationHandler.END

    await update.effective_message.reply_text(
        "💳 <b>Withdrawal</b>\n\n"
        f"💰 আপনার Balance: ৳{balance_amount:.2f}\n\n"
        "আপনি কত টাকা Withdraw করতে চান?\n"
        "শুধু Amount লিখুন।\n\n"
        "উদাহরণ: <code>100</code>\n\n"
        "❌ বাতিল করতে /cancel লিখুন।",
        parse_mode="HTML"
    )

    return WITHDRAW_AMOUNT


async def withdrawal_amount(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    try:
        amount = float(update.effective_message.text)

        if amount <= 0:
            raise ValueError

    except ValueError:
        await update.effective_message.reply_text(
            "❌ সঠিক Amount লিখুন।\n"
            "উদাহরণ: 100"
        )
        return WITHDRAW_AMOUNT

    user = update.effective_user
    balance_amount = get_balance(user.id)

    if amount > balance_amount:
        await update.effective_message.reply_text(
            f"❌ আপনার Balance ৳{balance_amount:.2f}।\n"
            "এর চেয়ে বেশি Withdraw করা যাবে না।"
        )
        return WITHDRAW_AMOUNT

    context.user_data["withdraw_amount"] = amount

    await update.effective_message.reply_text(
        "💳 Payment Method লিখুন:\n\n"
        "উদাহরণ:\n"
        "bKash\n"
        "Nagad\n"
        "Rocket"
    )

    return WITHDRAW_METHOD


async def withdrawal_method(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    method = update.effective_message.text.strip()

    if not method:
        await update.effective_message.reply_text(
            "❌ Payment Method লিখুন।"
        )
        return WITHDRAW_METHOD

    context.user_data["withdraw_method"] = method

    await update.effective_message.reply_text(
        "📱 আপনার bKash/Nagad/Rocket Number লিখুন:"
    )

    return WITHDRAW_NUMBER


async def withdrawal_number(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user = update.effective_user

    number = update.effective_message.text.strip()
    amount = context.user_data.get("withdraw_amount")
    method = context.user_data.get("withdraw_method")

    if not number:
        await update.effective_message.reply_text(
            "❌ সঠিক Number লিখুন।"
        )
        return WITHDRAW_NUMBER

    if not amount or not method:
        await update.effective_message.reply_text(
            "❌ Withdrawal তথ্য পাওয়া যায়নি। আবার চেষ্টা করুন।"
        )
        return ConversationHandler.END

    balance_amount = get_balance(user.id)

    if amount > balance_amount:
        await update.effective_message.reply_text(
            "❌ পর্যাপ্ত Balance নেই।"
        )
        return ConversationHandler.END

    # Reserve amount
    change_balance(user.id, -amount)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO withdrawals
        (user_id, amount, method, number, status, created_at)
        VALUES (?, ?, ?, ?, 'pending', ?)
    """, (
        user.id,
        amount,
        method,
        number,
        datetime.now().isoformat()
    ))

    conn.commit()
    withdrawal_id = cur.lastrowid
    conn.close()

    await update.effective_message.reply_text(
        "✅ <b>Withdrawal Request জমা হয়েছে!</b>\n\n"
        f"🆔 Request ID: {withdrawal_id}\n"
        f"💰 Amount: ৳{amount:.2f}\n"
        f"💳 Method: {method}\n"
        f"📱 Number: {number}\n\n"
        "⏳ Admin যাচাই করার পর Payment করা হবে।",
        parse_mode="HTML"
    )

    # Notify admin
    if ADMIN_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    "💳 <b>New Withdrawal Request</b>\n\n"
                    f"🆔 Request ID: {withdrawal_id}\n"
                    f"👤 User ID: {user.id}\n"
                    f"👤 Username: @{user.username or 'N/A'}\n"
                    f"💰 Amount: ৳{amount:.2f}\n"
                    f"💳 Method: {method}\n"
                    f"📱 Number: {number}"
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass

    context.user_data.pop("withdraw_amount", None)
    context.user_data.pop("withdraw_method", None)

    return ConversationHandler.END


# =========================================================
# HELP
# =========================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await update.effective_message.reply_text(
        "📖 <b>Help</b>\n\n"
        "/start — Bot চালু করুন\n"
        "/task — Task দেখুন\n"
        "/referral — Referral Link\n"
        "/balance — Balance দেখুন\n"
        "/withdraw — টাকা Withdraw\n"
        "/support — Support\n"
        "/channel — Channel\n"
        "/help — Help\n\n"
        "⚠️ কখনো OTP বা Password শেয়ার করবেন না।",
        parse_mode="HTML"
    )


# =========================================================
# SUPPORT
# =========================================================

async def support_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await update.effective_message.reply_text(
        "📞 <b>Support</b>\n\n"
        f"প্রয়োজনে যোগাযোগ করুন: {SUPPORT_USERNAME}",
        parse_mode="HTML"
    )


# =========================================================
# CHANNEL
# =========================================================

async def channel_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    keyboard = [
        [
            InlineKeyboardButton(
                "📢 আমাদের Channel",
                url=CHANNEL_URL
            )
        ]
    ]

    await update.effective_message.reply_text(
        "📢 আমাদের Official Channel:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================================================
# ADMIN - ADD TASK
# =========================================================

async def admin_addtask(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not is_admin(update.effective_user.id):
        await update.effective_message.reply_text(
            "❌ আপনি Admin নন।"
        )
        return

    if len(context.args) < 3:
        await update.effective_message.reply_text(
            "❌ Format:\n\n"
            "/addtask Title | Description | Reward\n\n"
            "উদাহরণ:\n"
            "/addtask YouTube Task | ভিডিও দেখুন | 10"
        )
        return

    raw = " ".join(context.args)
    parts = [x.strip() for x in raw.split("|")]

    if len(parts) < 3:
        await update.effective_message.reply_text(
            "❌ | দিয়ে ৩টি অংশ দিন:\n"
            "Title | Description | Reward"
        )
        return

    title = parts[0]
    description = parts[1]

    try:
        reward = float(parts[2])
    except ValueError:
        await update.effective_message.reply_text(
            "❌ Reward সংখ্যা হতে হবে।"
        )
        return

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO tasks
        (title, description, reward, created_at)
        VALUES (?, ?, ?, ?)
    """, (
        title,
        description,
        reward,
        datetime.now().isoformat()
    ))

    conn.commit()
    task_id = cur.lastrowid
    conn.close()

    await update.effective_message.reply_text(
        "✅ Task Added!\n\n"
        f"🆔 ID: {task_id}\n"
        f"📌 Title: {title}\n"
        f"💰 Reward: ৳{reward}"
    )


# =========================================================
# ADMIN - TASK LIST
# =========================================================

async def admin_tasks(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not is_admin(update.effective_user.id):
        await update.effective_message.reply_text(
            "❌ আপনি Admin নন।"
        )
        return

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM tasks ORDER BY id DESC"
    )

    rows = cur.fetchall()
    conn.close()

    if not rows:
        await update.effective_message.reply_text(
            "📭 কোনো Task নেই।"
        )
        return

    text = "📋 <b>All Tasks</b>\n\n"

    for row in rows:
        text += (
            f"🆔 {row['id']}\n"
            f"📌 {row['title']}\n"
            f"💰 ৳{row['reward']}\n\n"
        )

    await update.effective_message.reply_text(
        text,
        parse_mode="HTML"
    )


# =========================================================
# ADMIN - SUBMISSIONS
# =========================================================

async def admin_submissions(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not is_admin(update.effective_user.id):
        await update.effective_message.reply_text(
            "❌ আপনি Admin নন।"
        )
        return

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT * FROM submissions
        WHERE status = 'pending'
        ORDER BY id DESC
        LIMIT 10
    """)

    rows = cur.fetchall()
    conn.close()

    if not rows:
        await update.effective_message.reply_text(
            "📭 কোনো Pending Submission নেই।"
        )
        return

    text = "📥 <b>Pending Submissions</b>\n\n"

    for row in rows:
        text += (
            f"🆔 Submission: {row['id']}\n"
            f"👤 User: {row['user_id']}\n"
            f"📌 Task: {row['task_id']}\n"
            f"📄 Proof: {row['proof']}\n"
            "━━━━━━━━━━━━\n"
        )

    text += (
        "\nApprove করতে:\n"
        "<code>/approve SUBMISSION_ID</code>\n\n"
        "Reject করতে:\n"
        "<code>/reject SUBMISSION_ID</code>"
    )

    await update.effective_message.reply_text(
        text,
        parse_mode="HTML"
    )


# =========================================================
# ADMIN - APPROVE SUBMISSION
# =========================================================

async def admin_approve(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not is_admin(update.effective_user.id):
        await update.effective_message.reply_text(
            "❌ আপনি Admin নন।"
        )
        return

    if not context.args:
        await update.effective_message.reply_text(
            "❌ ব্যবহার করুন:\n"
            "/approve SUBMISSION_ID"
        )
        return

    try:
        submission_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text(
            "❌ সঠিক Submission ID দিন।"
        )
        return

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT submissions.*, tasks.reward
        FROM submissions
        JOIN tasks ON tasks.id = submissions.task_id
        WHERE submissions.id = ?
    """, (submission_id,))

    row = cur.fetchone()

    if not row:
        conn.close()

        await update.effective_message.reply_text(
            "❌ Submission পাওয়া যায়নি।"
        )
        return

    if row["status"] != "pending":
        conn.close()

        await update.effective_message.reply_text(
            "⚠️ এই Submission ইতোমধ্যে process করা হয়েছে।"
        )
        return

    reward = float(row["reward"])

    cur.execute("""
        UPDATE submissions
        SET status = 'approved'
        WHERE id = ?
    """, (submission_id,))

    cur.execute("""
        UPDATE users
        SET balance = balance + ?
        WHERE user_id = ?
    """, (
        reward,
        row["user_id"]
    ))

    conn.commit()
    conn.close()

    await update.effective_message.reply_text(
        "✅ Submission Approved!\n\n"
        f"🆔 Submission: {submission_id}\n"
        f"💰 Reward: ৳{reward:.2f}"
    )

    try:
        await context.bot.send_message(
            chat_id=row["user_id"],
            text=(
                "🎉 <b>Task Approved!</b>\n\n"
                f"💰 আপনার Balance-এ ৳{reward:.2f} যোগ হয়েছে।\n"
                f"💵 Current Balance: ৳{get_balance(row['user_id']):.2f}"
            ),
            parse_mode="HTML"
        )
    except Exception:
        pass


# =========================================================
# ADMIN - REJECT SUBMISSION
# =========================================================

async def admin_reject(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not is_admin(update.effective_user.id):
        await update.effective_message.reply_text(
            "❌ আপনি Admin নন।"
        )
        return

    if not context.args:
        await update.effective_message.reply_text(
            "❌ ব্যবহার করুন:\n"
            "/reject SUBMISSION_ID"
        )
        return

    try:
        submission_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text(
            "❌ সঠিক Submission ID দিন।"
        )
        return

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM submissions WHERE id = ?",
        (submission_id,)
    )

    row = cur.fetchone()

    if not row:
        conn.close()

        await update.effective_message.reply_text(
            "❌ Submission পাওয়া যায়নি।"
        )
        return

    if row["status"] != "pending":
        conn.close()

        await update.effective_message.reply_text(
            "⚠️ এই Submission ইতোমধ্যে process করা হয়েছে।"
        )
        return

    cur.execute("""
        UPDATE submissions
        SET status = 'rejected'
        WHERE id = ?
    """, (submission_id,))

    conn.commit()
    conn.close()

    await update.effective_message.reply_text(
        f"❌ Submission {submission_id} rejected."
    )

    try:
        await context.bot.send_message(
            chat_id=row["user_id"],
            text=(
                "❌ আপনার Task Proof Reject করা হয়েছে।\n\n"
                "সঠিকভাবে Task সম্পন্ন করে আবার চেষ্টা করতে পারেন।"
            )
        )
    except Exception:
        pass


# =========================================================
# ADMIN - WITHDRAWALS
# =========================================================

async def admin_withdrawals(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not is_admin(update.effective_user.id):
        await update.effective_message.reply_text(
            "❌ আপনি Admin নন।"
        )
        return

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT * FROM withdrawals
        WHERE status = 'pending'
        ORDER BY id DESC
        LIMIT 10
    """)

    rows = cur.fetchall()
    conn.close()

    if not rows:
        await update.effective_message.reply_text(
            "📭 কোনো Pending Withdrawal নেই।"
        )
        return

    text = "💳 <b>Pending Withdrawals</b>\n\n"

    for row in rows:
        text += (
            f"🆔 ID: {row['id']}\n"
            f"👤 User: {row['user_id']}\n"
            f"💰 Amount: ৳{row['amount']}\n"
            f"💳 Method: {row['method']}\n"
            f"📱 Number: {row['number']}\n"
            "━━━━━━━━━━━━\n"
        )

    await update.effective_message.reply_text(
        text,
        parse_mode="HTML"
    )


# =========================================================
# CALLBACK BUTTON
# =========================================================

async def button(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    q = update.callback_query

    # এখানে শুধু সাধারণ button callback handle হবে
    # do: callback ConversationHandler handle করবে

    if q.data == "tasks":
        await q.answer()
        await tasks(update, context)

    elif q.data == "balance":
        await q.answer()
        await show_balance(update, context)

    elif q.data == "referral":
        await q.answer()
        await referral(update, context)

    elif q.data == "withdraw":
        await q.answer()
        await q.message.reply_text(
            "💳 টাকা তুলতে /withdraw লিখুন।"
        )

    elif q.data == "help":
        await q.answer()
        await help_command(update, context)

    elif q.data == "support":
        await q.answer()
        await support_command(update, context)


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):
    print(
        "ERROR:",
        repr(context.error)
    )


# =========================================================
# MAIN
# =========================================================

def main():

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable পাওয়া যায়নি!"
        )

    init_db()

    # Render health server
    threading.Thread(
        target=run_health_server,
        daemon=True
    ).start()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # -----------------------------------------------------
    # TASK PROOF CONVERSATION
    # -----------------------------------------------------

    proof_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                do_task,
                pattern=r"^do:\d+$"
            )
        ],
        states={
            SUBMIT_PROOF: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    submit_proof
                )
            ]
        },
        fallbacks=[
            CommandHandler(
                "cancel",
                cancel
            )
        ],
        per_user=True,
        per_chat=True,
        per_message=False,
    )

    # -----------------------------------------------------
    # WITHDRAW CONVERSATION
    # -----------------------------------------------------

    wd_conv = ConversationHandler(
        entry_points=[
            CommandHandler(
                "withdraw",
                withdraw
            )
        ],
        states={
            WITHDRAW_AMOUNT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    withdrawal_amount
                )
            ],
            WITHDRAW_METHOD: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    withdrawal_method
                )
            ],
            WITHDRAW_NUMBER: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    withdrawal_number
                )
            ],
        },
        fallbacks=[
            CommandHandler(
                "cancel",
                cancel
            )
        ],
        per_user=True,
        per_chat=True,
        per_message=False,
    )

    # -----------------------------------------------------
    # COMMANDS
    # -----------------------------------------------------

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("task", tasks)
    )

    app.add_handler(
        CommandHandler("referral", referral)
    )

    app.add_handler(
        CommandHandler("balance", show_balance)
    )

    app.add_handler(
        CommandHandler("help", help_command)
    )

    app.add_handler(
        CommandHandler("support", support_command)
    )

    app.add_handler(
        CommandHandler("channel", channel_command)
    )

    # -----------------------------------------------------
    # CONVERSATIONS FIRST
    # -----------------------------------------------------

    # খুব গুরুত্বপূর্ণ:
    # proof_conv এবং wd_conv generic button-এর আগে থাকবে।

    app.add_handler(proof_conv)

    app.add_handler(wd_conv)

    # -----------------------------------------------------
    # ADMIN COMMANDS
    # -----------------------------------------------------

    app.add_handler(
        CommandHandler(
            "addtask",
            admin_addtask
        )
    )

    app.add_handler(
        CommandHandler(
            "admintasks",
            admin_tasks
        )
    )

    app.add_handler(
        CommandHandler(
            "submissions",
            admin_submissions
        )
    )

    app.add_handler(
        CommandHandler(
            "approve",
            admin_approve
        )
    )

    app.add_handler(
        CommandHandler(
            "reject",
            admin_reject
        )
    )

    app.add_handler(
        CommandHandler(
            "withdrawals",
            admin_withdrawals
        )
    )

    # -----------------------------------------------------
    # GENERAL CALLBACK BUTTON
    # -----------------------------------------------------

    # do: callback এখানে আসবে না,
    # কারণ proof_conv আগে do: ধরে ফেলবে।

    app.add_handler(
        CallbackQueryHandler(
            button,
            pattern=r"^(tasks|balance|referral|withdraw|help|support)$"
        )
    )

    # Error handler
    app.add_error_handler(error_handler)

    print("🤖 Income Taka Bot is starting...")

    app.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


# =========================================================
# START PROGRAM
# =========================================================

if __name__ == "__main__":
    main()
