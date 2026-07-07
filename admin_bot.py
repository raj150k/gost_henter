import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telethon import TelegramClient, events
from telethon.tl.functions.users import GetFullUserRequest
from telethon.errors import SessionPasswordNeededError

# ====== তোমার তথ্য ======
BOT_TOKEN = "8749787354:AAEdEIfgcex72ZWZEnMKRaGxPjjYitbZ-ps"    # BotFather থেকে টোকেন বসাও
ADMIN_ID = 8636937438                  # তোমার টেলিগ্রাম ID বসাও
# ========================

ACCOUNTS_FILE = "accounts.json"
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_REPLY = """
Hey {name} 🌸
👤 Username : @{username}

Welcome to {boss_name}'s Personal Assistant 🤖

📩 Your message has been received successfully.

Boss is currently offline or busy 💤
But don't worry — your message has been forwarded successfully ✅

💬 As soon as Boss comes online, you'll get a reply.

⏳ Please wait patiently...

😎 My Boss : {boss_name} 🤘
👑 Owner : @{boss_username}
⚡ Assistant : Ghost Hunter

✨ Thank you for messaging ✨
"""

def load_data():
    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE) as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(ACCOUNTS_FILE, "w") as f:
        json.dump(data, f, indent=4, default=str)

class AccountManager:
    def __init__(self):
        self.data = load_data()
        self.clients = {}
    
    def add_account(self, name, api_id, api_hash, phone):
        if name in self.data:
            return "❌ Account already exists!"
        self.data[name] = {
            "api_id": api_id,
            "api_hash": api_hash,
            "phone": phone,
            "users": {},
            "banned": [],
            "custom_reply": None,
            "enabled": True,
            "status": "stopped"
        }
        save_data(self.data)
        return f"✅ Account '{name}' added! Use /startaccount {name} to activate."
    
    def remove_account(self, name):
        if name not in self.data:
            return "❌ Account not found!"
        if name in self.clients:
            loop = asyncio.get_event_loop()
            loop.create_task(self.disconnect(name))
        del self.data[name]
        save_data(self.data)
        return f"✅ Account '{name}' removed!"
    
    async def disconnect(self, name):
        try:
            c = self.clients.pop(name, None)
            if c:
                await c.disconnect()
        except:
            pass
    
    def ban_user(self, name, user_id):
        if name not in self.data:
            return "❌ Account not found!"
        banned = set(self.data[name].get("banned", []))
        banned.add(user_id)
        self.data[name]["banned"] = list(banned)
        save_data(self.data)
        return f"✅ User {user_id} banned from '{name}'!"
    
    def unban_user(self, name, user_id):
        if name not in self.data:
            return "❌ Account not found!"
        banned = set(self.data[name].get("banned", []))
        banned.discard(user_id)
        self.data[name]["banned"] = list(banned)
        save_data(self.data)
        return f"✅ User {user_id} unbanned from '{name}'!"
    
    def set_reply(self, name, text):
        if name not in self.data:
            return "❌ Account not found!"
        self.data[name]["custom_reply"] = text
        save_data(self.data)
        return "✅ Custom reply set! Use {name}, {username}, {boss_name}, {boss_username}"
    
    def reset_reply(self, name):
        if name not in self.data:
            return "❌ Account not found!"
        self.data[name]["custom_reply"] = None
        save_data(self.data)
        return "✅ Default reply restored!"
    
    def get_list(self):
        if not self.data:
            return "❌ No accounts configured!"
        text = "📋 **Account List:**\n\n"
        for n, c in self.data.items():
            emoji = {"running": "🟢", "stopped": "🔴", "error": "🟡"}.get(c.get("status"), "⚪")
            text += f"{emoji} **{n}**\n"
            text += f"   ├ 👤 Users: {len(c.get('users', {}))}\n"
            text += f"   ├ 🚫 Banned: {len(c.get('banned', []))}\n"
            text += f"   └ 📱 {c.get('phone', 'N/A')}\n\n"
        return text

manager = AccountManager()

def create_handlers(client, account_name):
    @client.on(events.NewMessage(incoming=True))
    async def auto_reply(event):
        if not event.is_private:
            return
        
        cfg = manager.data.get(account_name)
        if not cfg or not cfg.get("enabled", True):
            return
        
        me = await client.get_me()
        full = await client(GetFullUserRequest(me.id))
        status = str(full.users[0].status).lower()
        
        if "offline" not in status and "empty" not in status:
            return
        
        sender = await event.get_sender()
        user_id = sender.id
        user_name = sender.first_name or "Unknown"
        username = sender.username or "No Username"
        
        if user_id in cfg.get("banned", []):
            return
        
        now = datetime.now()
        users = cfg.get("users", {})
        key = str(user_id)
        
        if key not in users:
            users[key] = {"count": 0, "time": now.isoformat()}
        
        data = users[key]
        last_time = datetime.fromisoformat(data["time"])
        
        if now - last_time > timedelta(minutes=30):
            data["count"] = 0
        
        if data["count"] >= 2:
            return
        
        custom = cfg.get("custom_reply")
        if custom:
            msg = custom.format(
                name=user_name,
                username=f"@{username}" if username != "No Username" else "No Username",
                boss_name=me.first_name or "Boss",
                boss_username=me.username or "boss"
            )
        else:
            msg = DEFAULT_REPLY.format(
                name=user_name,
                username=f"@{username}" if username != "No Username" else "No Username",
                boss_name=me.first_name or "Boss",
                boss_username=me.username or "boss"
            )
        
        reply = await event.reply(msg)
        data["count"] += 1
        data["time"] = now.isoformat()
        cfg["users"] = users
        save_data(manager.data)
        
        async def delete_later():
            await asyncio.sleep(300)
            try:
                await reply.delete()
            except:
                pass
        
        asyncio.create_task(delete_later())

async def start_account(name):
    cfg = manager.data.get(name)
    if not cfg:
        return "❌ Account not found!"
    if name in manager.clients:
        return "ℹ️ Already running!"
    
    try:
        os.makedirs("sessions", exist_ok=True)
        client = TelegramClient(f"sessions/{name}", cfg["api_id"], cfg["api_hash"])
        await client.connect()
        
        if not await client.is_user_authorized():
            await client.send_code_request(cfg["phone"])
            return f"📱 OTP sent to {cfg['phone']}. Use /verify {name} <code>"
        
        await client.start(phone=cfg["phone"])
        create_handlers(client, name)
        manager.clients[name] = client
        cfg["status"] = "running"
        save_data(manager.data)
        asyncio.create_task(client.run_until_disconnected())
        return f"✅ Account '{name}' is now running!"
    
    except SessionPasswordNeededError:
        return "🔑 2FA required! Use /verify2fa <name> <password>"
    except Exception as e:
        cfg["status"] = "error"
        save_data(manager.data)
        return f"❌ Error: {str(e)}"

async def verify_account(name, code):
    cfg = manager.data.get(name)
    if not cfg:
        return "❌ Account not found!"
    try:
        client = TelegramClient(f"sessions/{name}", cfg["api_id"], cfg["api_hash"])
        await client.connect()
        await client.sign_in(phone=cfg["phone"], code=code)
        create_handlers(client, name)
        manager.clients[name] = client
        cfg["status"] = "running"
        save_data(manager.data)
        asyncio.create_task(client.run_until_disconnected())
        return f"✅ Account '{name}' verified and running!"
    except SessionPasswordNeededError:
        return "🔑 2FA required! Use /verify2fa <name> <password>"
    except Exception as e:
        return f"❌ Error: {str(e)}"

async def verify_2fa(name, password):
    cfg = manager.data.get(name)
    if not cfg:
        return "❌ Account not found!"
    try:
        client = TelegramClient(f"sessions/{name}", cfg["api_id"], cfg["api_hash"])
        await client.connect()
        await client.sign_in(password=password)
        create_handlers(client, name)
        manager.clients[name] = client
        cfg["status"] = "running"
        save_data(manager.data)
        asyncio.create_task(client.run_until_disconnected())
        return f"✅ Account '{name}' logged in with 2FA!"
    except Exception as e:
        return f"❌ Error: {str(e)}"

async def stop_account(name):
    if name in manager.clients:
        try:
            await manager.clients.pop(name).disconnect()
        except:
            pass
    if name in manager.data:
        manager.data[name]["status"] = "stopped"
        save_data(manager.data)
    return f"✅ Account '{name}' stopped!"

# ========== Bot Commands ==========

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("❌ Unauthorized!")
    
    text = """
🤖 **Ghost Admin Bot**

**Commands:**
━━━━━━━━━━━━━━━━━━
📌 **Account:**
/addaccount <name> <api_id> <api_hash> <phone>
/removeaccount <name>
/startaccount <name>
/stopaccount <name>
/verify <name> <otp>
/verify2fa <name> <password>

📌 **User Control:**
/ban <name> <user_id>
/unban <name> <user_id>

📌 **Reply Customization:**
/setreply <name> <your_message>
/resetreply <name>

📌 **Info:**
/accounts
/stats <name>
━━━━━━━━━━━━━━━━━━

💡 Use {name}, {username}, {boss_name}, {boss_username} in custom reply
    """
    await update.message.reply_text(text, parse_mode="Markdown")

async def addaccount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if len(context.args) < 4:
        return await update.message.reply_text("❌ /addaccount <name> <api_id> <api_hash> <phone>")
    try:
        api_id = int(context.args[1])
    except:
        return await update.message.reply_text("❌ api_id must be a number!")
    result = manager.add_account(context.args[0], api_id, context.args[2], context.args[3])
    await update.message.reply_text(result)

async def removeaccount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args:
        return await update.message.reply_text("❌ /removeaccount <name>")
    await update.message.reply_text(manager.remove_account(context.args[0]))

async def startaccount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args:
        return await update.message.reply_text("❌ /startaccount <name>")
    result = await start_account(context.args[0])
    await update.message.reply_text(result)

async def stopaccount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args:
        return await update.message.reply_text("❌ /stopaccount <name>")
    result = await stop_account(context.args[0])
    await update.message.reply_text(result)

async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if len(context.args) < 2:
        return await update.message.reply_text("❌ /verify <name> <otp_code>")
    result = await verify_account(context.args[0], context.args[1])
    await update.message.reply_text(result)

async def verify2fa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if len(context.args) < 2:
        return await update.message.reply_text("❌ /verify2fa <name> <password>")
    result = await verify_2fa(context.args[0], " ".join(context.args[1:]))
    await update.message.reply_text(result)

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if len(context.args) < 2:
        return await update.message.reply_text("❌ /ban <name> <user_id>")
    try:
        result = manager.ban_user(context.args[0], int(context.args[1]))
        await update.message.reply_text(result)
    except:
        await update.message.reply_text("❌ Invalid user_id!")

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if len(context.args) < 2:
        return await update.message.reply_text("❌ /unban <name> <user_id>")
    try:
        result = manager.unban_user(context.args[0], int(context.args[1]))
        await update.message.reply_text(result)
    except:
        await update.message.reply_text("❌ Invalid user_id!")

async def setreply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if len(context.args) < 2:
        return await update.message.reply_text("❌ /setreply <name> <your_message>")
    result = manager.set_reply(context.args[0], " ".join(context.args[1:]))
    await update.message.reply_text(result)

async def resetreply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args:
        return await update.message.reply_text("❌ /resetreply <name>")
    result = manager.reset_reply(context.args[0])
    await update.message.reply_text(result)

async def accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    result = manager.get_list()
    await update.message.reply_text(result, parse_mode="Markdown")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args:
        return await update.message.reply_text("❌ /stats <name>")
    name = context.args[0]
    cfg = manager.data.get(name)
    if not cfg:
        return await update.message.reply_text("❌ Account not found!")
    
    text = f"""
📊 **Account: {name}**
━━━━━━━━━━━━━━━
📱 Phone: {cfg.get('phone', 'N/A')}
🔘 Status: {'🟢 Running' if cfg.get('status') == 'running' else '🔴 Stopped'}
👥 Total Users: {len(cfg.get('users', {}))}
🚫 Banned: {len(cfg.get('banned', []))}
💬 Reply: {'✅ Custom' if cfg.get('custom_reply') else '❌ Default'}
    """
    await update.message.reply_text(text, parse_mode="Markdown")

def main():
    os.makedirs("sessions", exist_ok=True)
    
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ ERROR: Please set your BOT_TOKEN in admin_bot.py!")
        return
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", start_cmd))
    app.add_handler(CommandHandler("addaccount", addaccount))
    app.add_handler(CommandHandler("removeaccount", removeaccount))
    app.add_handler(CommandHandler("startaccount", startaccount))
    app.add_handler(CommandHandler("stopaccount", stopaccount))
    app.add_handler(CommandHandler("verify", verify))
    app.add_handler(CommandHandler("verify2fa", verify2fa))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("setreply", setreply))
    app.add_handler(CommandHandler("resetreply", resetreply))
    app.add_handler(CommandHandler("accounts", accounts))
    app.add_handler(CommandHandler("stats", stats))
    
    print("🤖 Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
