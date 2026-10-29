import telebot, sqlite3, os, threading, datetime
from telebot import types
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
BKASH_NUMBER = os.getenv("BKASH_NUMBER", "017XXXXXXXX")
GROUP_ID = os.getenv("GROUP_ID", "")
bot = telebot.TeleBot(BOT_TOKEN)

app = Flask(__name__)
@app.route('/')
def home():
    return "✅ Bot is 24/7 Online - Group Notify + /id!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

db_lock = threading.Lock()
conn = sqlite3.connect("proxy.db", check_same_thread=False)
with db_lock:
    conn.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0)")
    conn.execute("CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, price REAL, stock INTEGER DEFAULT 0)")
    conn.execute("CREATE TABLE IF NOT EXISTS proxies (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER, proxy TEXT, status TEXT DEFAULT 'available', sold_to INTEGER, FOREIGN KEY(product_id) REFERENCES products(id))")
    conn.execute("CREATE TABLE IF NOT EXISTS deposits (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL, trxid TEXT, status TEXT DEFAULT 'pending')")
    conn.execute("CREATE TABLE IF NOT EXISTS purchases (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, proxy TEXT, product_name TEXT, price REAL, order_time TEXT)")
    conn.commit()

def get_cur(): return conn.cursor()
admin_temp = {}

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
    kb.add(types.InlineKeyboardButton("➕ Add New Product", callback_data="adm_add_product"), types.InlineKeyboardButton("📦 Add Stock", callback_data="adm_add_stock"))
    kb.add(types.InlineKeyboardButton("📦 Show Stock", callback_data="adm_stock"), types.InlineKeyboardButton("📥 Deposits", callback_data="adm_deps"))
    kb.add(types.InlineKeyboardButton("👥 Users", callback_data="adm_users"), types.InlineKeyboardButton("📋 All Codes", callback_data="adm_all_codes"))
    return kb

@bot.message_handler(commands=['start'])
def start(m):
    with db_lock:
        cur = get_cur()
        cur.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)", (m.from_user.id,))
        conn.commit()
    if m.from_user.id == ADMIN_ID:
        bot.send_message(m.chat.id, "✅ Bot 24/7 Ready! Group Notify ON!\nWelcome Admin!", reply_markup=admin_kb())
        bot.send_message(m.chat.id, "🔐 Admin Panel:", reply_markup=admin_inline())
    else:
        bot.send_message(m.chat.id, "✅ Welcome!", reply_markup=user_kb())

@bot.message_handler(commands=['id', 'groupid'])
def group_id_cmd(m):
    bot.reply_to(m, f"🆔 Chat ID: `{m.chat.id}`\nType: {m.chat.type}", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "💳 Balance")
def bal(m):
    with db_lock:
        cur = get_cur()
        cur.execute("SELECT balance FROM users WHERE user_id=?", (m.from_user.id,))
        row = cur.fetchone()
    bot.send_message(m.chat.id, f"💳 Balance: {row[0] if row else 0} TK")

@bot.message_handler(func=lambda m: m.text == "🛡️ Get Code")
def getcode(m):
    with db_lock:
        cur = get_cur()
        cur.execute("SELECT proxy, product_name FROM purchases WHERE user_id=? ORDER BY id DESC", (m.from_user.id,))
        rows = cur.fetchall()
    if not rows:
        bot.send_message(m.chat.id, "❌ No codes yet!")
    else:
        txt = "🛡️ Your Codes:\n\n"
        for proxy, name in rows:
            txt += f"*{name}*:\n`{proxy}`\n\n"
        bot.send_message(m.chat.id, txt, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "💰 Deposit")
def deposit(m):
    bot.send_message(m.chat.id, f"💰 *bKash Number (tap to copy):*\n\n`{BKASH_NUMBER}`\n\n👆 Tap to copy\n\nTaka pathiye likho:\n`Amount TrxID` Ex: `100 ABC123`", parse_mode="Markdown")
    bot.register_next_step_handler(m, deposit_step)

def deposit_step(m):
    try:
        parts = m.text.split()
        amount = float(parts[0])
        trxid = parts[1] if len(parts) > 1 else m.text
        with db_lock:
            cur = get_cur()
            cur.execute("INSERT INTO deposits (user_id, amount, trxid) VALUES (?, ?, ?)", (m.from_user.id, amount, trxid))
            conn.commit()
            cur.execute("SELECT id FROM deposits WHERE user_id=? AND trxid=? ORDER BY id DESC LIMIT 1", (m.from_user.id, trxid))
            dep_id = cur.fetchone()[0]
        bot.send_message(m.chat.id, "✅ Deposit request sent!")
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("✅ Approve", callback_data=f"dep_approve_{dep_id}"), types.InlineKeyboardButton("❌ Reject", callback_data=f"dep_reject_{dep_id}"))
        bot.send_message(ADMIN_ID, f"📥 *New Deposit!*\nUser: `{m.from_user.id}`\nAmount: {amount}\nTrxID: `{trxid}`\nID: {dep_id}", parse_mode="Markdown", reply_markup=kb)
    except:
        bot.send_message(m.chat.id, "❌ Wrong format! Ex: 100 TrxID123")

@bot.message_handler(func=lambda m: m.text == "🛍️ Buy Product")
def buy(m):
    with db_lock:
        cur = get_cur()
        cur.execute("SELECT id, name, price, stock FROM products WHERE stock > 0")
        rows = cur.fetchall()
    if not rows:
        bot.send_message(m.chat.id, "❌ Out of stock!")
        return
    kb = types.InlineKeyboardMarkup()
    for pid, name, price, stock in rows:
        kb.add(types.InlineKeyboardButton(f"{name} ৳{price} - {stock} stock", callback_data=f"buy_prod_{pid}"))
    bot.send_message(m.chat.id, "🛍️ *Available Products:*", parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("buy_prod_"))
def buy_prod_cb(c):
    pid = int(c.data.split("_")[2])
    with db_lock:
        cur = get_cur()
        cur.execute("SELECT name, price, stock FROM products WHERE id=?", (pid,))
        prod = cur.fetchone()
        if not prod or prod[2] <= 0:
            bot.answer_callback_query(c.id, "❌ Out of stock!")
            return
        pname, price, stock = prod
        cur.execute("SELECT balance FROM users WHERE user_id=?", (c.from_user.id,))
        bal_row = cur.fetchone()
        bal = bal_row[0] if bal_row else 0
        if bal < price:
            bot.answer_callback_query(c.id, f"❌ Need {price} TK")
            return
        cur.execute("SELECT id, proxy FROM proxies WHERE product_id=? AND status='available' LIMIT 1", (pid,))
        proxy_row = cur.fetchone()
        if not proxy_row:
            bot.answer_callback_query(c.id, "❌ No code found!")
            return
        proxy_id, proxy_code = proxy_row
        order_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (price, c.from_user.id))
        cur.execute("UPDATE proxies SET status='sold', sold_to=? WHERE id=?", (c.from_user.id, proxy_id))
        cur.execute("UPDATE products SET stock=stock-1 WHERE id=?", (pid,))
        cur.execute("INSERT INTO purchases (user_id, proxy, product_name, price, order_time) VALUES (?, ?, ?, ?, ?)", (c.from_user.id, proxy_code, pname, price, order_time))
        order_id = cur.lastrowid
        conn.commit()
        cur.execute("SELECT stock FROM products WHERE id=?", (pid,))
        new_stock = cur.fetchone()[0]

    bot.answer_callback_query(c.id, "✅ Purchased!")
    bot.send_message(c.message.chat.id, f"✅ *Bought {pname}!*\nOrder ID: `#{order_id}`\n\nCode:\n`{proxy_code}`\n\nPrice: ৳{price}\nRemaining: {new_stock} pcs", parse_mode="Markdown")

    if GROUP_ID:
        try:
            buyer_name = f"@{c.from_user.username}" if c.from_user.username else c.from_user.first_name
            group_msg = f"🛍️ *New Order!*\n\n📦 Product: *{pname}*\n🆔 Order ID: `#{order_id}`\n👤 Buyer: {buyer_name} (`{c.from_user.id}`)\n💰 Price: ৳{price}\n📊 Status: *Paid ✅*\n📦 Stock Left: *{new_stock} pcs*\n⏰ Time: {order_time}"
            bot.send_message(GROUP_ID, group_msg, parse_mode="Markdown")
        except Exception as e:
            print(f"Group send error: {e}")

@bot.message_handler(func=lambda m: m.text == "👤 My Profile")
def profile(m):
    with db_lock:
        cur = get_cur()
        cur.execute("SELECT balance FROM users WHERE user_id=?", (m.from_user.id,))
        row = cur.fetchone()
    bot.send_message(m.chat.id, f"👤 ID: {m.from_user.id}\nBalance: {row[0] if row else 0} TK")

@bot.message_handler(func=lambda m: m.text == "🔐 Admin Panel")
def admin_panel(m):
    if m.from_user.id == ADMIN_ID:
        bot.send_message(m.chat.id, "🔐 Admin Panel:", reply_markup=admin_inline())

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_"))
def admin_cb(c):
    if c.from_user.id != ADMIN_ID: return
    if c.data == "adm_add_product":
        bot.send_message(c.message.chat.id, "1️⃣ *Product Nam?* Ex: `9proxy 50mb`", parse_mode="Markdown")
        bot.register_next_step_handler(c.message, admin_add_product_name)
    elif c.data == "adm_add_stock":
        with db_lock:
            cur = get_cur()
            cur.execute("SELECT id, name, stock FROM products")
            rows = cur.fetchall()
        if not rows:
            bot.send_message(c.message.chat.id, "❌ Age product add koro!")
            return
        kb = types.InlineKeyboardMarkup()
        for pid, name, stock in rows:
            kb.add(types.InlineKeyboardButton(f"{name} - {stock} stock", callback_data=f"addstock_{pid}"))
        bot.send_message(c.message.chat.id, "Konta te stock add korba?", reply_markup=kb)
    elif c.data == "adm_stock":
        with db_lock:
            cur = get_cur()
            cur.execute("SELECT id, name, price, stock FROM products ORDER BY stock DESC")
            rows = cur.fetchall()
        txt = "📦 *Stock:*\n\n" if rows else "No products!"
        for pid, name, price, stock in rows:
            txt += f"ID:{pid} | {name} ৳{price}\nStock: *{stock}* pcs\n\n"
        bot.send_message(c.message.chat.id, txt, parse_mode="Markdown")
    elif c.data == "adm_deps":
        with db_lock:
            cur = get_cur()
            cur.execute("SELECT id, user_id, amount, trxid FROM deposits WHERE status='pending'")
            rows = cur.fetchall()
        if not rows:
            bot.send_message(c.message.chat.id, "No pending")
        else:
            for r in rows:
                kb = types.InlineKeyboardMarkup()
                kb.add(types.InlineKeyboardButton("✅ Approve", callback_data=f"dep_approve_{r[0]}"), types.InlineKeyboardButton("❌ Reject", callback_data=f"dep_reject_{r[0]}"))
                bot.send_message(c.message.chat.id, f"ID:{r[0]} User:`{r[1]}`\nAmount:{r[2]}\nTrxID: `{r[3]}`", parse_mode="Markdown", reply_markup=kb)
    elif c.data == "adm_users":
        with db_lock:
            cur = get_cur()
            cur.execute("SELECT COUNT(*) FROM users")
            cnt = cur.fetchone()[0]
        bot.send_message(c.message.chat.id, f"👥 Users: {cnt}")
    elif c.data == "adm_all_codes":
        with db_lock:
            cur = get_cur()
            cur.execute("SELECT p.name, pr.proxy, pr.status FROM proxies pr JOIN products p ON pr.product_id=p.id ORDER BY p.name LIMIT 20")
            rows = cur.fetchall()
        txt = "📋 All Codes:\n\n" if rows else "No codes!"
        for name, code, status in rows:
            icon = "✅" if status == 'available' else "❌"
            txt += f"{icon} {name}: `{code}` - {status}\n"
        bot.send_message(c.message.chat.id, txt, parse_mode="Markdown")

def admin_add_product_name(m):
    admin_temp[m.from_user.id] = {"name": m.text}
    bot.send_message(m.chat.id, "2️⃣ *Dam koto?* Ex: `10`", parse_mode="Markdown")
    bot.register_next_step_handler(m, admin_add_product_price)

def admin_add_product_price(m):
    try:
        price = float(m.text)
        name = admin_temp[m.from_user.id]["name"]
        with db_lock:
            cur = get_cur()
            cur.execute("INSERT INTO products (name, price, stock) VALUES (?, ?, 0)", (name, price))
            conn.commit()
            pid = cur.lastrowid
        bot.send_message(m.chat.id, f"✅ Product Added!\nID:{pid}\nName: {name}\nPrice: ৳{price}\nStock: 0 pcs", parse_mode="Markdown")
        admin_temp.pop(m.from_user.id, None)
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Error: {e}")

@bot.callback_query_handler(func=lambda c: c.data.startswith("addstock_"))
def addstock_cb(c):
    pid = int(c.data.split("_")[1])
    admin_temp[c.from_user.id] = {"product_id": pid}
    with db_lock:
        cur = get_cur()
        cur.execute("SELECT name FROM products WHERE id=?", (pid,))
        name = cur.fetchone()[0]
    bot.send_message(c.message.chat.id, f"📦 *{name}* e stock add korba\nEk line e ekta code dao!", parse_mode="Markdown")
    bot.register_next_step_handler(c.message, admin_add_stock_codes)

def admin_add_stock_codes(m):
    try:
        pid = admin_temp[m.from_user.id]["product_id"]
        codes = [line.strip() for line in m.text.split("\n") if line.strip()]
        if not codes:
            codes = [m.text.strip()]
        with db_lock:
            cur = get_cur()
            for code in codes:
                cur.execute("INSERT INTO proxies (product_id, proxy, status) VALUES (?, ?, 'available')", (pid, code))
            cur.execute("UPDATE products SET stock=stock+? WHERE id=?", (len(codes), pid))
            conn.commit()
            cur.execute("SELECT name, stock, price FROM products WHERE id=?", (pid,))
            name, stock, price = cur.fetchone()
        bot.send_message(m.chat.id, f"✅ Stock Added!\nProduct: {name}\nAdded: {len(codes)} pcs\nTotal: *{stock}* pcs", parse_mode="Markdown")
        admin_temp.pop(m.from_user.id, None)
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Error: {e}")

@bot.callback_query_handler(func=lambda c: c.data.startswith("dep_"))
def dep_cb(c):
    if c.from_user.id != ADMIN_ID: return
    _, action, did = c.data.split("_")
    did = int(did)
    with db_lock:
        cur = get_cur()
        cur.execute("SELECT user_id, amount FROM deposits WHERE id=?", (did,))
        row = cur.fetchone()
        if not row: return
        uid, amt = row
        if action == "approve":
            cur.execute("UPDATE deposits SET status='approved' WHERE id=?", (did,))
            cur.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)", (uid,))
            cur.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amt, uid))
            conn.commit()
            bot.send_message(uid, f"✅ Approved! {amt} TK added!")
            bot.edit_message_text(f"✅ Approved ID:{did}", c.message.chat.id, c.message.message_id)
        else:
            cur.execute("UPDATE deposits SET status='rejected' WHERE id=?", (did,))
            conn.commit()
            bot.send_message(uid, f"❌ Rejected ID:{did}")
            bot.edit_message_text(f"❌ Rejected ID:{did}", c.message.chat.id, c.message.message_id)
    bot.answer_callback_query(c.id, "Done!")

def run_bot():
    print("Bot Started... GROUP NOTIFY + /id")
    bot.infinity_polling()

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    print("Flask Started for Render 24/7...")
    run_flask()
