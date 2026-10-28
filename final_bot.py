import telebot, sqlite3, os
from telebot import types

BOT_TOKEN = os.getenv("BOT_TOKEN", "9233916179:AAG9sI6Uwuvug8V8JHUEPg6bPOU8X0fHuXs")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7486233932"))
BKASH_NUMBER = os.getenv("BKASH_NUMBER", "01787344884")

bot = telebot.TeleBot(BOT_TOKEN)
conn = sqlite3.connect("proxy.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0)")
cur.execute("CREATE TABLE IF NOT EXISTS proxies (id INTEGER PRIMARY KEY AUTOINCREMENT, proxy TEXT, price REAL, status TEXT DEFAULT 'available', sold_to INTEGER)")
cur.execute("CREATE TABLE IF NOT EXISTS deposits (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL, trxid TEXT, status TEXT DEFAULT 'pending')")
cur.execute("CREATE TABLE IF NOT EXISTS purchases (user_id INTEGER, proxy TEXT)")
conn.commit()

def user_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🛍️ Buy Product", "💰 Deposit")
    kb.add("💳 Balance", "🛡️ Get Code")
    kb.add("👤 My Profile")
    return kb

def admin_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🔐 Admin Panel", "💳 Balance")
    kb.add("🛍️ Buy Product", "💰 Deposit")
    kb.add("👤 My Profile", "🛡️ Get Code")
    return kb

def admin_inline():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("➕ Proxy Add", callback_data="adm_add"), types.InlineKeyboardButton("📦 Stock", callback_data="adm_stock"))
    kb.add(types.InlineKeyboardButton("📥 Deposits", callback_data="adm_deps"), types.InlineKeyboardButton("👥 Users", callback_data="adm_users"))
    kb.add(types.InlineKeyboardButton("📢 Broadcast", callback_data="adm_bc"))
    return kb

@bot.message_handler(commands=['start'])
def start(m):
    cur.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (m.from_user.id,))
    conn.commit()
    if m.from_user.id == ADMIN_ID:
        bot.send_message(m.chat.id, f"Welcome Admin {m.from_user.first_name}! Bot Ready!", reply_markup=admin_kb())
        bot.send_message(m.chat.id, "🔐 Admin Panel:", reply_markup=admin_inline())
    else:
        bot.send_message(m.chat.id, f"Welcome {m.from_user.first_name}! Balance diye proxy kinte parba.", reply_markup=user_kb())

@bot.message_handler(func=lambda m: m.text=="🔐 Admin Panel")
def open_admin(m):
    if m.from_user.id != ADMIN_ID: return
    bot.send_message(m.chat.id, "🔐 Admin Panel:", reply_markup=admin_inline())

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_"))
def admin_cb(c):
    if c.from_user.id != ADMIN_ID: return
    if c.data == "adm_stock":
        cur.execute("SELECT COUNT(*) FROM proxies WHERE status='available'")
        av = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM proxies WHERE status='sold'")
        sold = cur.fetchone()[0]
        bot.send_message(c.message.chat.id, f"📦 Stock\nAvailable: {av}\nSold: {sold}")
    elif c.data == "adm_deps":
        cur.execute("SELECT id, user_id, amount, trxid FROM deposits WHERE status='pending' ORDER BY id DESC LIMIT 10")
        rows = cur.fetchall()
        if not rows:
            bot.send_message(c.message.chat.id, "No pending deposit")
            return
        for r in rows:
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("✅ Approve", callback_data=f"ap_{r[0]}"), types.InlineKeyboardButton("❌ Reject", callback_data=f"rj_{r[0]}"))
            bot.send_message(c.message.chat.id, f"ID:{r[0]}\nUser:{r[1]}\nAmt:{r[2]} BDT\nTrxID:{r[3]}", reply_markup=kb)
    elif c.data == "adm_add":
        msg = bot.send_message(c.message.chat.id, "Proxy dao format e:\n`ip:port:user:pass price`\nExample:\n`103.20.1.1:8080:u1:p1 100`\nMultiple line dite paro.", parse_mode="Markdown")
        bot.register_next_step_handler(msg, add_proxy_multi)
    elif c.data == "adm_users":
        cur.execute("SELECT COUNT(*) FROM users")
        total = cur.fetchone()[0]
        bot.send_message(c.message.chat.id, f"Total Users: {total}")
    elif c.data == "adm_bc":
        msg = bot.send_message(c.message.chat.id, "Broadcast message likho, sob user er kache jabe:")
        bot.register_next_step_handler(msg, do_broadcast)

def add_proxy_multi(m):
    count=0
    for line in m.text.split("\n"):
        line=line.strip()
        if not line: continue
        try:
            if " " in line:
                proxy, price = line.rsplit(" ",1)
                price=float(price)
            else:
                proxy=line
                price=100
            cur.execute("INSERT INTO proxies (proxy, price) VALUES (?,?)", (proxy, price))
            count+=1
        except: pass
    conn.commit()
    bot.send_message(m.chat.id, f"✅ {count} ta proxy add hoise!")

def do_broadcast(m):
    cur.execute("SELECT user_id FROM users")
    sent=0
    for (uid,) in cur.fetchall():
        try:
            bot.send_message(uid, f"📢 Notice:\n{m.text}")
            sent+=1
        except: pass
    bot.send_message(m.chat.id, f"Broadcast done! {sent} jon ke pathano hoise.")

@bot.message_handler(func=lambda m: m.text=="💰 Deposit")
def deposit(m):
    msg = bot.send_message(m.chat.id, "Amount likho (Min 100 BDT):")
    bot.register_next_step_handler(msg, deposit_amt)

def deposit_amt(m):
    try:
        amt=float(m.text)
        msg=bot.send_message(m.chat.id, f"{amt} BDT {BKASH_NUMBER} e send koro\nEkhon TrxID dao:")
        bot.register_next_step_handler(msg, lambda x: save_dep(x, amt))
    except: bot.send_message(m.chat.id, "Sothik number likho!")

def save_dep(m, amt):
    cur.execute("INSERT INTO deposits (user_id, amount, trxid) VALUES (?,?,?)", (m.from_user.id, amt, m.text.strip()))
    conn.commit()
    did=cur.lastrowid
    bot.send_message(m.chat.id, "✅ Request admin er kache geche!")
    kb=types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✅ Approve", callback_data=f"ap_{did}"), types.InlineKeyboardButton("❌ Reject", callback_data=f"rj_{did}"))
    bot.send_message(ADMIN_ID, f"🔔 New Deposit!\nUser: {m.from_user.id}\nAmt: {amt} BDT\nTrxID: {m.text}", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text=="🛍️ Buy Product")
def buy_list(m):
    cur.execute("SELECT id, proxy, price FROM proxies WHERE status='available' ORDER BY price ASC LIMIT 10")
    rows=cur.fetchall()
    if not rows:
        bot.send_message(m.chat.id, "😔 Stock khali! Admin Panel -> Proxy Add")
        return
    kb=types.InlineKeyboardMarkup()
    for r in rows:
        kb.add(types.InlineKeyboardButton(f"{r[1][:20]} - {r[2]} BDT", callback_data=f"buy_{r[0]}"))
    bot.send_message(m.chat.id, "🛍️ Available Proxy List:", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text=="💳 Balance")
def balance_check(m):
    cur.execute("SELECT balance FROM users WHERE user_id=?", (m.from_user.id,))
    row=cur.fetchone()
    bal=row[0] if row else 0
    bot.send_message(m.chat.id, f"💳 Your Balance\n💰 {bal} BDT", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text=="👤 My Profile")
def profile(m):
    cur.execute("SELECT balance FROM users WHERE user_id=?", (m.from_user.id,))
    bal=cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM purchases WHERE user_id=?", (m.from_user.id,))
    total=cur.fetchone()[0]
    bot.send_message(m.chat.id, f"👤 Profile\nID: {m.from_user.id}\nBalance: {bal} BDT\nTotal Bought: {total}")

@bot.message_handler(func=lambda m: m.text=="🛡️ Get Code")
def getcode(m):
    cur.execute("SELECT proxy FROM purchases WHERE user_id=? ORDER BY rowid DESC LIMIT 10", (m.from_user.id,))
    rows=cur.fetchall()
    if not rows: bot.send_message(m.chat.id, "Kono proxy kino nai!")
    else:
        txt="\n\n".join([f"`{r[0]}`" for r in rows])
        bot.send_message(m.chat.id, f"🛡️ Your Proxies:\n\n{txt}", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: True)
def all_cb(c):
    if c.data.startswith("ap_"):
        did=int(c.data.split("_")[1])
        cur.execute("SELECT user_id, amount FROM deposits WHERE id=?", (did,))
        row=cur.fetchone()
        if not row: return
        uid, amt=row
        cur.execute("UPDATE deposits SET status='approved' WHERE id=?", (did,))
        cur.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amt, uid))
        conn.commit()
        bot.edit_message_text(f"✅ Approved ID {did} - {amt} BDT", c.message.chat.id, c.message.message_id)
        try: bot.send_message(uid, f"✅ Tomar {amt} BDT Deposit Approved!")
        except: pass
    elif c.data.startswith("rj_"):
        did=int(c.data.split("_")[1])
        cur.execute("UPDATE deposits SET status='rejected' WHERE id=?", (did,))
        conn.commit()
        bot.edit_message_text(f"❌ Rejected ID {did}", c.message.chat.id, c.message.message_id)
    elif c.data.startswith("buy_"):
        pid=int(c.data.split("_")[1])
        cur.execute("SELECT balance FROM users WHERE user_id=?", (c.from_user.id,))
        bal=cur.fetchone()[0]
        cur.execute("SELECT price, proxy FROM proxies WHERE id=? AND status='available'", (pid,))
        row=cur.fetchone()
        if not row:
            bot.answer_callback_query(c.id, "Already sold!", show_alert=True)
            return
        price, proxy=row
        if bal < price:
            bot.answer_callback_query(c.id, f"Balance kom! {bal} ache, {price} lagbe", show_alert=True)
            return
        cur.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (price, c.from_user.id))
        cur.execute("UPDATE proxies SET status='sold', sold_to=? WHERE id=?", (c.from_user.id, pid))
        cur.execute("INSERT INTO purchases (user_id, proxy) VALUES (?,?)", (c.from_user.id, proxy))
        conn.commit()
        bot.send_message(c.message.chat.id, f"✅ Purchase Success!\n\nYour Proxy:\n`{proxy}`", parse_mode="Markdown")

print("Bot Started... 24/7 Ready!")
bot.infinity_polling()
