import os
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, MessageHandler, filters
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

CHANNEL_URL = "https://t.me/YOUR_CHANNEL"
SUPPORT_USERNAME = "@YOUR_ADMIN_USERNAME"
DB_FILE = "bot.db"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")
if not ADMIN_ID:
    raise RuntimeError("ADMIN_ID is missing")

ADD_TITLE, ADD_DESC, ADD_REWARD, ADD_LINK = range(4)
WITHDRAW_AMOUNT, WITHDRAW_METHOD, WITHDRAW_ACCOUNT = range(10, 13)
SUBMIT_PROOF = 20


def db():
    return sqlite3.connect(DB_FILE)


def init_db():
    con = db()
    cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        username TEXT, first_name TEXT,
        balance REAL DEFAULT 0,
        referrals INTEGER DEFAULT 0,
        referred_by INTEGER,
        joined_at TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS tasks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        reward REAL NOT NULL,
        link TEXT,
        active INTEGER DEFAULT 1,
        created_at TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS submissions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER, user_id INTEGER,
        proof TEXT, status TEXT DEFAULT 'pending',
        created_at TEXT,
        UNIQUE(task_id, user_id)
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS withdrawals(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, amount REAL,
        method TEXT, account TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )""")
    con.commit()
    con.close()


def add_user(user, referrer_id=None):
    con = db()
    cur = con.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (user.id,))
    exists = cur.fetchone()
    if not exists:
        valid_ref = None
        if referrer_id and referrer_id != user.id:
            cur.execute("SELECT user_id FROM users WHERE user_id=?", (referrer_id,))
            if cur.fetchone():
                valid_ref = referrer_id
        cur.execute("""INSERT INTO users
            (user_id, username, first_name, referred_by, joined_at)
            VALUES (?, ?, ?, ?, ?)""",
            (user.id, user.username or "", user.first_name or "",
             valid_ref, datetime.utcnow().isoformat()))
        if valid_ref:
            cur.execute("UPDATE users SET referrals=referrals+1 WHERE user_id=?", (valid_ref,))
    else:
        cur.execute("UPDATE users SET username=?, first_name=? WHERE user_id=?",
                    (user.username or "", user.first_name or "", user.id))
    con.commit()
    con.close()


def balance(user_id):
    con = db()
    row = con.execute("SELECT balance FROM users WHERE user_id=?", (user_id,)).fetchone()
    con.close()
    return float(row[0]) if row else 0.0


def change_balance(user_id, amount):
    con = db()
    con.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, user_id))
    con.commit()
    con.close()


def is_admin(update):
    return update.effective_user and update.effective_user.id == ADMIN_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ref = None
    if context.args and context.args[0].startswith("ref_"):
        try:
            ref = int(context.args[0][4:])
        except ValueError:
            pass
    add_user(update.effective_user, ref)
    kb = [
        [InlineKeyboardButton("💰 Tasks", callback_data="tasks"),
         InlineKeyboardButton("💵 Balance", callback_data="balance")],
        [InlineKeyboardButton("👥 Referral", callback_data="referral"),
         InlineKeyboardButton("💳 Withdraw", callback_data="withdraw")],
        [InlineKeyboardButton("📢 Channel", url=CHANNEL_URL)],
        [InlineKeyboardButton("📞 Support", url="https://t.me/" + SUPPORT_USERNAME.lstrip("@"))]
    ]
    await update.effective_message.reply_text(
        f"🤖 *Income Taka — Online Earning*\n\n"
        f"আসসালামু আলাইকুম, {update.effective_user.first_name}! 👋\n\n"
        "বৈধ ও স্বচ্ছ Task সম্পন্ন করে Reward পাওয়ার ব্যবস্থা এখানে থাকবে।\n"
        "⚠️ OTP, Password বা কোনো গোপন তথ্য দেবেন না।",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb)
    )


async def tasks(update, context):
    add_user(update.effective_user)
    con = db()
    rows = con.execute("SELECT id,title,description,reward,link FROM tasks WHERE active=1 ORDER BY id DESC").fetchall()
    con.close()
    if not rows:
        await update.effective_message.reply_text("📭 এখন কোনো active Task নেই।")
        return
    for tid, title, desc, reward, link in rows:
        kb = [[InlineKeyboardButton(f"✅ Complete Task #{tid}", callback_data=f"do:{tid}")]]
        if link:
            kb.insert(0, [InlineKeyboardButton("🔗 Open Task", url=link)])
        await update.effective_message.reply_text(
            f"💰 *{title}*\n\n{desc}\n\n🎁 Reward: ৳{reward:.2f}",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb)
        )


async def referral(update, context):
    add_user(update.effective_user)
    me = await context.bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{update.effective_user.id}"
    con = db()
    row = con.execute("SELECT referrals FROM users WHERE user_id=?", (update.effective_user.id,)).fetchone()
    con.close()
    count = row[0] if row else 0
    await update.effective_message.reply_text(
        f"👥 *Referral*\n\nআপনার লিংক:\n`{link}`\n\n"
        f"👤 Referrals: {count}\n\n"
        "Referral reward Admin-এর নির্ধারিত নিয়ম অনুযায়ী দেওয়া হবে।",
        parse_mode="Markdown"
    )


async def show_balance(update, context):
    add_user(update.effective_user)
    await update.effective_message.reply_text(f"💵 আপনার Balance: ৳{balance(update.effective_user.id):.2f}")


async def do_task(update, context):
    q = update.callback_query
    await q.answer()
    tid = int(q.data.split(":")[1])
    con = db()
    task = con.execute("SELECT title,reward FROM tasks WHERE id=? AND active=1", (tid,)).fetchone()
    old = con.execute("SELECT id FROM submissions WHERE task_id=? AND user_id=?",
                      (tid, q.from_user.id)).fetchone()
    con.close()
    if not task:
        await q.message.reply_text("❌ Task পাওয়া যায়নি।")
        return
    if old:
        await q.message.reply_text("⏳ আপনি এই Task-এর proof আগে জমা দিয়েছেন।")
        return
    context.user_data["submit_task_id"] = tid
    await q.message.reply_text(
        f"📝 *{task[0]}*\n\nTask সম্পন্ন করার পর আপনার proof/link এখানে পাঠান।\n"
        "Admin যাচাই করার পর reward যোগ হবে।",
        parse_mode="Markdown"
    )


async def submit_proof(update, context):
    tid = context.user_data.pop("submit_task_id", None)
    if not tid:
        return
    proof = update.message.text.strip()
    if len(proof) < 3:
        await update.message.reply_text("❌ Valid proof দিন।")
        return
    con = db()
    task = con.execute("SELECT title,reward FROM tasks WHERE id=? AND active=1", (tid,)).fetchone()
    try:
        con.execute("""INSERT INTO submissions(task_id,user_id,proof,created_at)
                       VALUES(?,?,?,?,?)""",
                    (tid, update.effective_user.id, proof, datetime.utcnow().isoformat()))
    except sqlite3.IntegrityError:
        con.close()
        await update.message.reply_text("⏳ Proof আগে জমা হয়েছে।")
        return
    con.commit()
    con.close()
    await update.message.reply_text("✅ Proof জমা হয়েছে। Admin যাচাই করবেন।")
    await context.bot.send_message(
        ADMIN_ID,
        f"📥 *New Task Proof*\nTask: #{tid} — {task[0]}\n"
        f"User: {update.effective_user.id} (@{update.effective_user.username or 'no_username'})\n"
        f"Reward: ৳{task[1]:.2f}\nProof: {proof}\n\n"
        f"Approve: /approve {tid} {update.effective_user.id}\n"
        f"Reject: /reject {tid} {update.effective_user.id}",
        parse_mode="Markdown"
    )


async def withdraw(update, context):
    add_user(update.effective_user)
    if balance(update.effective_user.id) <= 0:
        await update.message.reply_text("💳 আপনার Balance 0। আগে বৈধ Task সম্পন্ন করুন।")
        return WITHDRAW_AMOUNT
    context.user_data["withdraw_step"] = True
    await update.message.reply_text(
        f"💳 আপনার Balance: ৳{balance(update.effective_user.id):.2f}\n\n"
        "কত টাকা Withdraw করতে চান? শুধু সংখ্যা লিখুন।"
    )
    return WITHDRAW_AMOUNT


async def withdraw_amount(update, context):
    try:
        amount = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ শুধু টাকার পরিমাণ লিখুন।")
        return WITHDRAW_AMOUNT
    if amount <= 0 or amount > balance(update.effective_user.id):
        await update.message.reply_text("❌ Balance-এর মধ্যে একটি সঠিক পরিমাণ দিন।")
        return WITHDRAW_AMOUNT
    context.user_data["wd_amount"] = amount
    await update.message.reply_text("💳 Payment method লিখুন (যেমন bKash/Nagad)।")
    return WITHDRAW_METHOD


async def withdraw_method(update, context):
    context.user_data["wd_method"] = update.message.text.strip()
    await update.message.reply_text("📱 আপনার payment number/account দিন।")
    return WITHDRAW_ACCOUNT


async def withdraw_account(update, context):
    user = update.effective_user
    amount = context.user_data["wd_amount"]
    method = context.user_data["wd_method"]
    account = update.message.text.strip()
    con = db()
    con.execute("""INSERT INTO withdrawals(user_id,amount,method,account,created_at)
                   VALUES(?,?,?,?,?)""",
                (user.id, amount, method, account, datetime.utcnow().isoformat()))
    con.commit()
    con.close()
    context.user_data.clear()
    await update.message.reply_text("✅ Withdraw request জমা হয়েছে। Admin যাচাই করবেন।")
    await context.bot.send_message(
        ADMIN_ID,
        f"💳 *New Withdraw*\nID: see /withdrawals\nUser: {user.id}\n"
        f"Amount: ৳{amount:.2f}\nMethod: {method}\nAccount: {account}",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


async def cancel(update, context):
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END


# ---------------- ADMIN ----------------

async def admin(update, context):
    if not is_admin(update):
        return
    await update.message.reply_text(
        "🛠 *Admin Panel*\n\n"
        "/addtask — নতুন Task\n"
        "/tasks_admin — সব Task\n"
        "/submissions — pending proofs\n"
        "/approve TASK_ID USER_ID\n"
        "/reject TASK_ID USER_ID\n"
        "/users — user count\n"
        "/addbalance USER_ID AMOUNT\n"
        "/withdrawals — pending withdrawals\n"
        "/pay WD_ID — mark paid\n"
        "/rejectwd WD_ID — reject withdrawal",
        parse_mode="Markdown"
    )


async def addtask_start(update, context):
    if not is_admin(update):
        return ConversationHandler.END
    await update.message.reply_text("Task-এর title লিখুন:")
    return ADD_TITLE


async def addtask_title(update, context):
    context.user_data["t_title"] = update.message.text.strip()
    await update.message.reply_text("Task-এর বিস্তারিত description লিখুন:")
    return ADD_DESC


async def addtask_desc(update, context):
    context.user_data["t_desc"] = update.message.text.strip()
    await update.message.reply_text("Reward কত? যেমন 5 বা 10")
    return ADD_REWARD


async def addtask_reward(update, context):
    try:
        r = float(update.message.text.strip())
        if r <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ সঠিক সংখ্যা দিন।")
        return ADD_REWARD
    context.user_data["t_reward"] = r
    await update.message.reply_text("Task link দিন। Link না থাকলে `-` লিখুন।")
    return ADD_LINK


async def addtask_link(update, context):
    link = update.message.text.strip()
    if link == "-":
        link = ""
    con = db()
    con.execute("""INSERT INTO tasks(title,description,reward,link,created_at)
                   VALUES(?,?,?,?,?)""",
                (context.user_data["t_title"], context.user_data["t_desc"],
                 context.user_data["t_reward"], link, datetime.utcnow().isoformat()))
    con.commit()
    con.close()
    context.user_data.clear()
    await update.message.reply_text("✅ Task তৈরি হয়েছে। /tasks দিয়ে দেখা যাবে।")
    return ConversationHandler.END


async def tasks_admin(update, context):
    if not is_admin(update):
        return
    con = db()
    rows = con.execute("SELECT id,title,reward,active FROM tasks ORDER BY id DESC").fetchall()
    con.close()
    if not rows:
        await update.message.reply_text("কোনো Task নেই।")
        return
    text = "\n".join([f"#{r[0]} — {r[1]} — ৳{r[2]:.2f} — {'ON' if r[3] else 'OFF'}" for r in rows])
    await update.message.reply_text(text)


async def submissions(update, context):
    if not is_admin(update):
        return
    con = db()
    rows = con.execute("""SELECT s.id,s.task_id,s.user_id,s.proof,t.reward
                         FROM submissions s JOIN tasks t ON t.id=s.task_id
                         WHERE s.status='pending' ORDER BY s.id DESC""").fetchall()
    con.close()
    if not rows:
        await update.message.reply_text("📭 Pending proof নেই।")
        return
    for sid, tid, uid, proof, reward in rows:
        await update.message.reply_text(
            f"📥 Submission #{sid}\nTask #{tid}\nUser: {uid}\nReward: ৳{reward:.2f}\nProof: {proof}\n\n"
            f"/approve {tid} {uid}\n/reject {tid} {uid}"
        )


async def approve(update, context):
    if not is_admin(update) or len(context.args) != 2:
        return
    tid, uid = map(int, context.args)
    con = db()
    row = con.execute("""SELECT s.id,t.reward FROM submissions s JOIN tasks t ON t.id=s.task_id
                         WHERE s.task_id=? AND s.user_id=? AND s.status='pending'""", (tid, uid)).fetchone()
    if not row:
        con.close()
        await update.message.reply_text("❌ Pending submission পাওয়া যায়নি।")
        return
    sid, reward = row
    con.execute("UPDATE submissions SET status='approved' WHERE id=?", (sid,))
    con.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (reward, uid))
    con.commit()
    con.close()
    await update.message.reply_text(f"✅ Approved. User {uid} পেল ৳{reward:.2f}")
    await context.bot.send_message(uid, f"🎉 আপনার Task approved!\n💰 Reward: ৳{reward:.2f}")


async def reject(update, context):
    if not is_admin(update) or len(context.args) != 2:
        return
    tid, uid = map(int, context.args)
    con = db()
    cur = con.execute("""UPDATE submissions SET status='rejected'
                        WHERE task_id=? AND user_id=? AND status='pending'""", (tid, uid))
    con.commit()
    con.close()
    await update.message.reply_text("❌ Submission rejected." if cur.rowcount else "Submission পাওয়া যায়নি।")
    if cur.rowcount:
        await context.bot.send_message(uid, f"❌ আপনার Task #{tid} proof reject হয়েছে।")


async def users(update, context):
    if not is_admin(update):
        return
    con = db()
    count = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total = con.execute("SELECT COALESCE(SUM(balance),0) FROM users").fetchone()[0]
    con.close()
    await update.message.reply_text(f"👥 Users: {count}\n💰 Total balance: ৳{total:.2f}")


async def addbalance(update, context):
    if not is_admin(update) or len(context.args) != 2:
        return
    uid, amount = int(context.args[0]), float(context.args[1])
    change_balance(uid, amount)
    await update.message.reply_text(f"✅ User {uid} balance changed by ৳{amount:.2f}")


async def withdrawals(update, context):
    if not is_admin(update):
        return
    con = db()
    rows = con.execute("""SELECT id,user_id,amount,method,account,status
                         FROM withdrawals WHERE status='pending' ORDER BY id DESC""").fetchall()
    con.close()
    if not rows:
        await update.message.reply_text("📭 Pending withdrawal নেই।")
        return
    for r in rows:
        await update.message.reply_text(
            f"💳 Withdrawal #{r[0]}\nUser: {r[1]}\nAmount: ৳{r[2]:.2f}\n"
            f"Method: {r[3]}\nAccount: {r[4]}\n\n"
            f"/pay {r[0]}\n/rejectwd {r[0]}"
        )


async def pay(update, context):
    if not is_admin(update) or len(context.args) != 1:
        return
    wid = int(context.args[0])
    con = db()
    row = con.execute("SELECT user_id,amount FROM withdrawals WHERE id=? AND status='pending'", (wid,)).fetchone()
    if not row:
        con.close()
        await update.message.reply_text("❌ Withdrawal পাওয়া যায়নি।")
        return
    uid, amount = row
    if balance(uid) < amount:
        con.close()
        await update.message.reply_text("❌ User balance এখন যথেষ্ট নয়।")
        return
    con.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (amount, uid))
    con.execute("UPDATE withdrawals SET status='paid' WHERE id=?", (wid,))
    con.commit()
    con.close()
    await update.message.reply_text(f"✅ Withdrawal #{wid} marked as PAID.")
    await context.bot.send_message(uid, f"✅ আপনার ৳{amount:.2f} Withdraw request paid হয়েছে।")


async def rejectwd(update, context):
    if not is_admin(update) or len(context.args) != 1:
        return
    wid = int(context.args[0])
    con = db()
    cur = con.execute("UPDATE withdrawals SET status='rejected' WHERE id=? AND status='pending'", (wid,))
    con.commit()
    con.close()
    await update.message.reply_text("❌ Withdrawal rejected." if cur.rowcount else "Withdrawal পাওয়া যায়নি।")


async def button(update, context):
    q = update.callback_query
    await q.answer()
    if q.data == "tasks":
        await tasks(update, context)
    elif q.data == "balance":
        await show_balance(update, context)
    elif q.data == "referral":
        await referral(update, context)
    elif q.data == "withdraw":
        await q.message.reply_text("💳 টাকা তুলতে /withdraw লিখুন।")
    elif q.data.startswith("do:"):
        await do_task(update, context)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Income Taka Bot is running!")
    def log_message(self, format, *args):
        pass


def health_server():
    port = int(os.environ.get("PORT", "10000"))
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()


def main():
    init_db()
    threading.Thread(target=health_server, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("task", tasks))
    app.add_handler(CommandHandler("tasks", tasks))
    app.add_handler(CommandHandler("referral", referral))
    app.add_handler(CommandHandler("balance", show_balance))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("tasks_admin", tasks_admin))
    app.add_handler(CommandHandler("submissions", submissions))
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(CommandHandler("reject", reject))
    app.add_handler(CommandHandler("users", users))
    app.add_handler(CommandHandler("addbalance", addbalance))
    app.add_handler(CommandHandler("withdrawals", withdrawals))
    app.add_handler(CommandHandler("pay", pay))
    app.add_handler(CommandHandler("rejectwd", rejectwd))
    app.add_handler(CallbackQueryHandler(button))

    add_conv = ConversationHandler(
        entry_points=[CommandHandler("addtask", addtask_start)],
        states={
            ADD_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, addtask_title)],
            ADD_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, addtask_desc)],
            ADD_REWARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, addtask_reward)],
            ADD_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, addtask_link)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    wd_conv = ConversationHandler(
        entry_points=[CommandHandler("withdraw", withdraw)],
        states={
            WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_amount)],
            WITHDRAW_METHOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_method)],
            WITHDRAW_ACCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_account)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    proof_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(do_task, pattern=r"^do:\d+$")],
        states={SUBMIT_PROOF: [MessageHandler(filters.TEXT & ~filters.COMMAND, submit_proof)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(add_conv)
    app.add_handler(wd_conv)
    app.add_handler(proof_conv)
    app.run_polling()


if __name__ == "__main__":
    main()
