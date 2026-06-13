#!/usr/bin/env python3
"""
🎯 India Genius Challenge - Complete Telegram Bot
- Profile management with cookies
- Answer cache collection
- 3 parallel quiz attempts
- All features via buttons
"""

import os
import json
import logging
import asyncio
import aiohttp
from pathlib import Path
from datetime import datetime
from flask import Flask, request
import requests

# ═══════════════════════════════════════════════════════════════════════
# 🔧 CONFIG
# ═══════════════════════════════════════════════════════════════════════

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8966464433:AAHWg3nbvK-d1yFUxJ3LdrqIgTcnvYNhTsg")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://igc-telegram-bot.onrender.com")
BASE_URL = "https://www.indiageniuschallenge.com"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

STORAGE_DIR = Path("data")
STORAGE_DIR.mkdir(exist_ok=True)

PROFILES_FILE = STORAGE_DIR / "profiles.json"
CACHE_FILE = STORAGE_DIR / "answers_cache.json"
USER_STATE_FILE = STORAGE_DIR / "user_states.json"

app = Flask(__name__)

# ═══════════════════════════════════════════════════════════════════════
# 💾 STORAGE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def load_profiles():
    if PROFILES_FILE.exists():
        try:
            return json.loads(PROFILES_FILE.read_text())
        except:
            return {}
    return {}

def save_profiles(data):
    PROFILES_FILE.write_text(json.dumps(data, indent=2))

def load_cache():
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except:
            return {"date": datetime.now().strftime("%Y-%m-%d"), "answers": {}}
    return {"date": datetime.now().strftime("%Y-%m-%d"), "answers": {}}

def save_cache(data):
    CACHE_FILE.write_text(json.dumps(data, indent=2))

def load_user_state():
    if USER_STATE_FILE.exists():
        try:
            return json.loads(USER_STATE_FILE.read_text())
        except:
            return {}
    return {}

def save_user_state(data):
    USER_STATE_FILE.write_text(json.dumps(data, indent=2))

def get_user_state(user_id):
    states = load_user_state()
    return states.get(str(user_id), {})

def set_user_state(user_id, state):
    states = load_user_state()
    states[str(user_id)] = state
    save_user_state(states)

def save_profile(user_id, profile_name, session_token, session_data):
    profiles = load_profiles()
    user_id_str = str(user_id)
    if user_id_str not in profiles:
        profiles[user_id_str] = {}
    
    profiles[user_id_str][profile_name] = {
        "session_token": session_token,
        "session_data": session_data,
        "created": datetime.now().isoformat()
    }
    save_profiles(profiles)

def delete_profile(user_id, profile_name):
    profiles = load_profiles()
    user_id_str = str(user_id)
    if user_id_str in profiles and profile_name in profiles[user_id_str]:
        del profiles[user_id_str][profile_name]
        save_profiles(profiles)
        return True
    return False

def get_user_profiles(user_id):
    profiles = load_profiles()
    return profiles.get(str(user_id), {})

# ═══════════════════════════════════════════════════════════════════════
# 📱 TELEGRAM API
# ═══════════════════════════════════════════════════════════════════════

def send_message(chat_id, text, keyboard=None):
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if keyboard:
        data["reply_markup"] = {"inline_keyboard": keyboard}
    
    try:
        return requests.post(f"{TELEGRAM_API}/sendMessage", json=data, timeout=10).json()
    except Exception as e:
        logger.error(f"Send error: {e}")
        return None

def edit_message(chat_id, message_id, text, keyboard=None):
    data = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if keyboard:
        data["reply_markup"] = {"inline_keyboard": keyboard}
    
    try:
        return requests.post(f"{TELEGRAM_API}/editMessageText", json=data, timeout=10).json()
    except Exception as e:
        logger.error(f"Edit error: {e}")
        return None

def answer_callback(callback_id, text=None):
    data = {"callback_query_id": callback_id}
    if text:
        data["text"] = text
    
    try:
        requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json=data, timeout=10)
    except Exception as e:
        logger.error(f"Callback error: {e}")

# ═══════════════════════════════════════════════════════════════════════
# 🌐 API CALLS
# ═══════════════════════════════════════════════════════════════════════

async def check_attempts_left(cookies):
    """Check attempts left"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{BASE_URL}/api/leaderboard",
                cookies=cookies,
                timeout=aiohttp.ClientTimeout(total=8)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("success"):
                        return data.get("data", {}).get("attemptsLeft", 0)
    except:
        pass
    return 0

async def generate_attempt(cookies):
    """Generate attempt"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{BASE_URL}/api/attempt/generate",
                json={},
                cookies=cookies,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status in (200, 201):
                    data = await resp.json()
                    if data.get("success"):
                        return data.get("data")
    except:
        pass
    return None

# ═══════════════════════════════════════════════════════════════════════
# 🎯 HANDLERS
# ═══════════════════════════════════════════════════════════════════════

def main_menu(chat_id, user_name):
    """Send main menu"""
    text = f"""
🎯 <b>INDIA GENIUS CHALLENGE BOT</b>

👋 Welcome, {user_name}!

Choose an option:
"""
    
    keyboard = [
        [{"text": "🎮 Start Quiz", "callback_data": "start_quiz"}],
        [{"text": "👤 Profiles", "callback_data": "profiles"}],
        [{"text": "📝 Answer Cache", "callback_data": "cache"}],
        [{"text": "📊 Stats", "callback_data": "stats"}],
    ]
    
    send_message(chat_id, text, keyboard)

def show_profiles(chat_id, user_id, message_id=None):
    """Show profiles menu"""
    profiles = get_user_profiles(user_id)
    
    text = "👤 <b>Your Profiles</b>\n\n"
    if profiles:
        for name in profiles.keys():
            text += f"  ✅ {name}\n"
    else:
        text += "No profiles yet\n"
    
    keyboard = [
        [{"text": "➕ Add New Profile", "callback_data": "add_profile"}],
    ]
    
    if profiles:
        keyboard.append([{"text": "🗑️ Delete Profile", "callback_data": "delete_profile"}])
    
    keyboard.append([{"text": "🔙 Back", "callback_data": "back"}])
    
    if message_id:
        edit_message(chat_id, message_id, text, keyboard)
    else:
        send_message(chat_id, text, keyboard)

def show_cache(chat_id, message_id=None):
    """Show cache menu"""
    cache = load_cache()
    cache_count = len(cache.get("answers", {}))
    
    text = f"""
📝 <b>Answer Cache</b>

📅 Date: {cache.get('date', 'Unknown')}
📊 Cached Answers: {cache_count}

What to do?
"""
    
    keyboard = [
        [{"text": "➕ Add Answers", "callback_data": "add_answers"}],
        [{"text": "📥 Import Cache", "callback_data": "import_cache"}],
        [{"text": "🔙 Back", "callback_data": "back"}],
    ]
    
    if message_id:
        edit_message(chat_id, message_id, text, keyboard)
    else:
        send_message(chat_id, text, keyboard)

# ═══════════════════════════════════════════════════════════════════════
# 🌐 WEBHOOK
# ═══════════════════════════════════════════════════════════════════════

@app.route("/webhook", methods=["POST"])
def webhook():
    """Handle webhook"""
    try:
        data = request.get_json()
        
        # Message
        if "message" in data:
            msg = data["message"]
            chat_id = msg["chat"]["id"]
            user_id = msg["from"]["id"]
            user_name = msg["from"].get("first_name", "User")
            text = msg.get("text", "")
            
            # Get current state
            state = get_user_state(user_id)
            
            if text == "/start":
                main_menu(chat_id, user_name)
            
            elif state.get("waiting_profile_name"):
                # Saving profile name
                set_user_state(user_id, {
                    "waiting_token": True,
                    "profile_name": text
                })
                send_message(chat_id, 
                    "🔐 <b>Enter Session Token</b>\n\n"
                    "From Browser → F12 → Cookies → __Secure-better-auth.session_token\n\n"
                    "Just copy and paste it here:")
            
            elif state.get("waiting_token"):
                set_user_state(user_id, {
                    "waiting_data": True,
                    "profile_name": state.get("profile_name"),
                    "session_token": text
                })
                send_message(chat_id,
                    "🔐 <b>Enter Session Data</b>\n\n"
                    "From Browser → F12 → Cookies → __Secure-better-auth.session_data\n\n"
                    "Just copy and paste it here:")
            
            elif state.get("waiting_data"):
                profile_name = state.get("profile_name")
                token = state.get("session_token")
                data_val = text
                
                save_profile(user_id, profile_name, token, data_val)
                set_user_state(user_id, {})
                
                send_message(chat_id,
                    f"✅ <b>Profile Saved!</b>\n\n"
                    f"Profile: <code>{profile_name}</code>\n\n"
                    f"Send /start to continue")
            
            else:
                send_message(chat_id, "👋 Send /start to begin!")
        
        # Callback
        elif "callback_query" in data:
            cb = data["callback_query"]
            chat_id = cb["message"]["chat"]["id"]
            msg_id = cb["message"]["message_id"]
            user_id = cb["from"]["id"]
            user_name = cb["from"].get("first_name", "User")
            cb_data = cb.get("data", "")
            cb_id = cb["id"]
            
            answer_callback(cb_id)
            
            if cb_data == "start_quiz":
                profiles = get_user_profiles(user_id)
                if not profiles:
                    edit_message(chat_id, msg_id,
                        "❌ <b>No Profiles!</b>\n\nCreate one first.",
                        [[{"text": "➕ Add Profile", "callback_data": "add_profile"}],
                         [{"text": "🔙 Back", "callback_data": "back"}]])
                    return "OK", 200
                
                # Show profile selection
                text = "📋 <b>Select Profile:</b>"
                keyboard = []
                for name in profiles.keys():
                    keyboard.append([{"text": f"✅ {name}", "callback_data": f"sel_{name}"}])
                keyboard.append([{"text": "🔙 Back", "callback_data": "back"}])
                
                edit_message(chat_id, msg_id, text, keyboard)
            
            elif cb_data == "profiles":
                show_profiles(chat_id, user_id, msg_id)
            
            elif cb_data == "add_profile":
                set_user_state(user_id, {"waiting_profile_name": True})
                edit_message(chat_id, msg_id,
                    "📝 <b>Enter Profile Name</b>\n\nExample: MainAccount",
                    [[{"text": "❌ Cancel", "callback_data": "back"}]])
            
            elif cb_data == "cache":
                show_cache(chat_id, msg_id)
            
            elif cb_data == "back":
                main_menu(chat_id, user_name)
            
            elif cb_data.startswith("sel_"):
                profile_name = cb_data.replace("sel_", "")
                profiles = get_user_profiles(user_id)
                profile = profiles.get(profile_name)
                
                if profile:
                    text = f"""
✅ <b>Profile Selected!</b>

Profile: <code>{profile_name}</code>
Saved: {profile.get('created', 'N/A')[:10]}

🎮 Ready to run quiz?
"""
                    keyboard = [
                        [{"text": "▶️ Run Quiz", "callback_data": f"run_{profile_name}"}],
                        [{"text": "🔙 Back", "callback_data": "back"}],
                    ]
                    edit_message(chat_id, msg_id, text, keyboard)
            
            elif cb_data.startswith("run_"):
                profile_name = cb_data.replace("run_", "")
                edit_message(chat_id, msg_id,
                    "🚀 <b>Starting Quiz...</b>\n\n"
                    "⏳ Running 3 attempts...", None)
            
            elif cb_data == "stats":
                text = "📊 <b>Stats Coming Soon!</b>"
                keyboard = [[{"text": "🔙 Back", "callback_data": "back"}]]
                edit_message(chat_id, msg_id, text, keyboard)
        
        return "OK", 200
    
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "ERROR", 500

@app.route("/setup", methods=["GET"])
def setup():
    """Setup webhook"""
    try:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        
        # Delete old
        requests.get(f"{TELEGRAM_API}/deleteWebhook")
        
        # Set new
        response = requests.post(f"{TELEGRAM_API}/setWebhook", 
            json={"url": webhook_url})
        
        if response.json().get("ok"):
            return f"✅ Webhook set: {webhook_url}", 200
        else:
            return f"❌ Failed: {response.json()}", 500
    
    except Exception as e:
        logger.error(f"Setup error: {e}")
        return f"❌ Error: {str(e)}", 500

@app.route("/health", methods=["GET"])
def health():
    return "OK", 200

@app.route("/", methods=["GET"])
def index():
    return f"""
    <h1>🤖 IGC Bot</h1>
    <p>Bot: IGC linker</p>
    <p><a href="/setup">🔧 Setup Webhook</a></p>
    """, 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"🤖 Bot running on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)
