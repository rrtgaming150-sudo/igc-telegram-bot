#!/usr/bin/env python3
"""
🎯 India Genius Challenge - Telegram Bot (Webhook Version)
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from flask import Flask, request
import requests

# ═══════════════════════════════════════════════════════════════════════
# 🔧 CONFIGURATION
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
app = Flask(__name__)

logger.info(f"Bot Token: {BOT_TOKEN[:20]}...")
logger.info(f"Webhook URL: {WEBHOOK_URL}/webhook")

# ═══════════════════════════════════════════════════════════════════════
# 💾 STORAGE
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

def get_user_profiles(user_id):
    profiles = load_profiles()
    return profiles.get(str(user_id), {})

def save_user_profile(user_id, profile_name, session_token, session_data):
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

# ═══════════════════════════════════════════════════════════════════════
# 📱 TELEGRAM API
# ═══════════════════════════════════════════════════════════════════════

def send_message(chat_id, text, keyboard=None):
    """Send message"""
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    
    if keyboard:
        data["reply_markup"] = {"inline_keyboard": keyboard}
    
    try:
        response = requests.post(f"{TELEGRAM_API}/sendMessage", json=data, timeout=10)
        return response.json()
    except Exception as e:
        logger.error(f"Send error: {e}")
        return None

def edit_message(chat_id, message_id, text, keyboard=None):
    """Edit message"""
    data = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML"
    }
    
    if keyboard:
        data["reply_markup"] = {"inline_keyboard": keyboard}
    
    try:
        response = requests.post(f"{TELEGRAM_API}/editMessageText", json=data, timeout=10)
        return response.json()
    except Exception as e:
        logger.error(f"Edit error: {e}")
        return None

def answer_callback(callback_id, text=None):
    """Answer callback"""
    data = {"callback_query_id": callback_id}
    if text:
        data["text"] = text
    
    try:
        requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json=data, timeout=10)
    except Exception as e:
        logger.error(f"Callback error: {e}")

# ═══════════════════════════════════════════════════════════════════════
# 🎯 HANDLERS
# ═══════════════════════════════════════════════════════════════════════

def send_main_menu(chat_id, user_name):
    """Send main menu"""
    text = f"""
╔══════════════════════════════════════╗
║ 🎯 INDIA GENIUS CHALLENGE - BOT 🎯  ║
║  Run 3 Parallel Quiz Attempts       ║
╚══════════════════════════════════════╝

👋 Welcome, {user_name}!
"""
    
    keyboard = [
        [{"text": "🎮 Start Quiz", "callback_data": "quiz_menu"}],
        [{"text": "👤 Manage Profiles", "callback_data": "profile_menu"}],
        [{"text": "📊 View Stats", "callback_data": "view_stats"}],
    ]
    
    send_message(chat_id, text, keyboard)

# ═══════════════════════════════════════════════════════════════════════
# 🌐 WEBHOOK
# ═══════════════════════════════════════════════════════════════════════

@app.route("/webhook", methods=["POST"])
def webhook():
    """Handle webhook updates"""
    try:
        data = request.get_json()
        logger.info(f"Webhook received: {data}")
        
        # Message
        if "message" in data:
            message = data["message"]
            chat_id = message["chat"]["id"]
            user_id = message["from"]["id"]
            user_name = message["from"].get("first_name", "User")
            text = message.get("text", "")
            
            logger.info(f"Message from {user_id}: {text}")
            
            if text == "/start":
                send_main_menu(chat_id, user_name)
            else:
                send_message(chat_id, f"👋 You said: {text}\n\nUse /start to begin!")
        
        # Callback
        elif "callback_query" in data:
            callback = data["callback_query"]
            chat_id = callback["message"]["chat"]["id"]
            message_id = callback["message"]["message_id"]
            user_id = callback["from"]["id"]
            user_name = callback["from"].get("first_name", "User")
            callback_data = callback.get("data", "")
            callback_id = callback["id"]
            
            logger.info(f"Callback from {user_id}: {callback_data}")
            answer_callback(callback_id)
            
            if callback_data == "quiz_menu":
                profiles = get_user_profiles(user_id)
                if not profiles:
                    text = "❌ <b>No Profiles!</b>\n\nCreate one first."
                    keyboard = [
                        [{"text": "➕ Add Profile", "callback_data": "add_profile"}],
                        [{"text": "🔙 Back", "callback_data": "back_menu"}],
                    ]
                else:
                    text = "📋 <b>Select Profile:</b>"
                    keyboard = []
                    for name in profiles.keys():
                        keyboard.append([{"text": f"✅ {name}", "callback_data": f"select_{name}"}])
                    keyboard.append([{"text": "🔙 Back", "callback_data": "back_menu"}])
                
                edit_message(chat_id, message_id, text, keyboard)
            
            elif callback_data == "profile_menu":
                profiles = get_user_profiles(user_id)
                text = "👤 <b>Profiles</b>\n\n"
                if profiles:
                    for name in profiles.keys():
                        text += f"  • {name}\n"
                else:
                    text += "<i>No profiles</i>\n"
                
                keyboard = [
                    [{"text": "➕ Add Profile", "callback_data": "add_profile"}],
                    [{"text": "🔙 Back", "callback_data": "back_menu"}],
                ]
                
                edit_message(chat_id, message_id, text, keyboard)
            
            elif callback_data == "add_profile":
                send_message(chat_id, "📝 <b>Enter Profile Name:</b>\n\nExample: MainAccount")
            
            elif callback_data == "back_menu":
                send_main_menu(chat_id, user_name)
            
            elif callback_data == "view_stats":
                text = "📊 <b>Stats Coming Soon!</b>"
                keyboard = [
                    [{"text": "🔙 Back", "callback_data": "back_menu"}],
                ]
                edit_message(chat_id, message_id, text, keyboard)
            
            elif callback_data.startswith("select_"):
                profile_name = callback_data.replace("select_", "")
                text = f"✅ <b>Profile Selected!</b>\n\n{profile_name}\n\n🎮 Ready to start?"
                keyboard = [
                    [{"text": "▶️ Start Quiz", "callback_data": "run_quiz"}],
                    [{"text": "🔙 Back", "callback_data": "back_menu"}],
                ]
                edit_message(chat_id, message_id, text, keyboard)
            
            elif callback_data == "run_quiz":
                text = "🚀 <b>Starting Quiz...</b>\n\n⏳ Running 3 attempts..."
                edit_message(chat_id, message_id, text, None)
        
        return "OK", 200
    
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "ERROR", 500

@app.route("/setup", methods=["GET"])
def setup():
    """Setup webhook"""
    try:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        logger.info(f"Setting up webhook: {webhook_url}")
        
        # Remove old webhook
        requests.get(f"{TELEGRAM_API}/deleteWebhook")
        
        # Set new webhook
        data = {"url": webhook_url}
        response = requests.post(f"{TELEGRAM_API}/setWebhook", json=data)
        
        logger.info(f"Setup response: {response.json()}")
        
        if response.json().get("ok"):
            return f"✅ Webhook set to: {webhook_url}", 200
        else:
            return f"❌ Failed: {response.json()}", 500
    
    except Exception as e:
        logger.error(f"Setup error: {e}")
        return f"❌ Error: {str(e)}", 500

@app.route("/health", methods=["GET"])
def health():
    """Health check"""
    return "OK", 200

@app.route("/", methods=["GET"])
def index():
    """Index page"""
    return f"""
    <h1>🤖 India Genius Challenge Bot</h1>
    <p>Bot Token: {BOT_TOKEN[:20]}...</p>
    <p><a href="/setup">Setup Webhook</a></p>
    <p><a href="/health">Health Check</a></p>
    """, 200

# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"🤖 Bot running on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)
