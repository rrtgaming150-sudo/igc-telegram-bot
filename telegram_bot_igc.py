#!/usr/bin/env python3
"""
🎯 India Genius Challenge - Telegram Bot (Webhook Version - Python 3.14 Compatible)
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from flask import Flask, request
import aiohttp
import asyncio
import requests

# ═══════════════════════════════════════════════════════════════════════
# 🔧 CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8989521653:AAGGnpq4bX_U4pQbTSjpdEZbjACUpD6jEnI")
BASE_URL = "https://www.indiageniuschallenge.com"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

STORAGE_DIR = Path("data")
STORAGE_DIR.mkdir(exist_ok=True)

PROFILES_FILE = STORAGE_DIR / "profiles.json"
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
# 📱 TELEGRAM API HELPERS
# ═══════════════════════════════════════════════════════════════════════

def send_message(chat_id, text, keyboard=None):
    """Send a message to user"""
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    
    if keyboard:
        data["reply_markup"] = {
            "inline_keyboard": keyboard
        }
    
    try:
        response = requests.post(f"{TELEGRAM_API}/sendMessage", json=data, timeout=10)
        return response.json()
    except Exception as e:
        logger.error(f"Send message error: {e}")
        return None

def edit_message(chat_id, message_id, text, keyboard=None):
    """Edit a message"""
    data = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML"
    }
    
    if keyboard:
        data["reply_markup"] = {
            "inline_keyboard": keyboard
        }
    
    try:
        response = requests.post(f"{TELEGRAM_API}/editMessageText", json=data, timeout=10)
        return response.json()
    except Exception as e:
        logger.error(f"Edit message error: {e}")
        return None

def answer_callback(callback_query_id, text=None, show_alert=False):
    """Answer callback query"""
    data = {
        "callback_query_id": callback_query_id,
        "show_alert": show_alert
    }
    if text:
        data["text"] = text
    
    try:
        requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json=data, timeout=10)
    except Exception as e:
        logger.error(f"Callback error: {e}")

# ═══════════════════════════════════════════════════════════════════════
# 🤖 HANDLERS
# ═══════════════════════════════════════════════════════════════════════

def handle_start(chat_id, user_name):
    """Handle /start command"""
    text = f"""
╔══════════════════════════════════════╗
║ 🎯 INDIA GENIUS CHALLENGE - BOT 🎯  ║
║  Run 3 Parallel Quiz Attempts       ║
╚══════════════════════════════════════╝

👋 Welcome, {user_name}!

Choose what you'd like to do:
"""
    
    keyboard = [
        [{"text": "🎮 Start Quiz", "callback_data": "quiz_menu"}],
        [{"text": "👤 Manage Profiles", "callback_data": "profile_menu"}],
        [{"text": "📊 View Stats", "callback_data": "view_stats"}],
    ]
    
    send_message(chat_id, text, keyboard)

def handle_quiz_menu(chat_id, message_id, user_id):
    """Show quiz menu"""
    profiles = get_user_profiles(user_id)
    
    if not profiles:
        text = "❌ <b>No Profiles Found!</b>\n\nPlease create a profile first."
        keyboard = [
            [{"text": "➕ Add Profile", "callback_data": "add_profile"}],
            [{"text": "🔙 Back", "callback_data": "back_menu"}],
        ]
        edit_message(chat_id, message_id, text, keyboard)
        return
    
    keyboard = []
    for profile_name in profiles.keys():
        keyboard.append([{"text": f"✅ {profile_name}", "callback_data": f"select_{profile_name}"}])
    keyboard.append([{"text": "🔙 Back", "callback_data": "back_menu"}])
    
    edit_message(chat_id, message_id, "📋 <b>Select Profile:</b>", keyboard)

def handle_profile_menu(chat_id, message_id, user_id):
    """Show profile menu"""
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

def handle_add_profile(chat_id):
    """Start adding profile"""
    text = "📝 <b>Enter Profile Name</b>\n\nSend the profile name:"
    send_message(chat_id, text)

def handle_back_menu(chat_id, message_id, user_id, user_name):
    """Go back to main menu"""
    text = f"""
╔══════════════════════════════════════╗
║ 🎯 INDIA GENIUS CHALLENGE - BOT 🎯  ║
║  Run 3 Parallel Quiz Attempts       ║
╚══════════════════════════════════════╝

👋 Welcome, {user_name}!

Choose what you'd like to do:
"""
    
    keyboard = [
        [{"text": "🎮 Start Quiz", "callback_data": "quiz_menu"}],
        [{"text": "👤 Manage Profiles", "callback_data": "profile_menu"}],
        [{"text": "📊 View Stats", "callback_data": "view_stats"}],
    ]
    
    edit_message(chat_id, message_id, text, keyboard)

# ═══════════════════════════════════════════════════════════════════════
# 🌐 WEBHOOK ENDPOINT
# ═══════════════════════════════════════════════════════════════════════

@app.route("/webhook", methods=["POST"])
def webhook():
    """Handle incoming webhook"""
    try:
        data = request.get_json()
        
        # Handle message
        if "message" in data:
            message = data["message"]
            chat_id = message["chat"]["id"]
            user_id = message["from"]["id"]
            user_name = message["from"].get("first_name", "User")
            text = message.get("text", "")
            
            if text == "/start":
                handle_start(chat_id, user_name)
        
        # Handle callback query
        elif "callback_query" in data:
            callback = data["callback_query"]
            chat_id = callback["message"]["chat"]["id"]
            message_id = callback["message"]["message_id"]
            user_id = callback["from"]["id"]
            user_name = callback["from"].get("first_name", "User")
            callback_data = callback.get("data", "")
            callback_id = callback["id"]
            
            answer_callback(callback_id)
            
            if callback_data == "quiz_menu":
                handle_quiz_menu(chat_id, message_id, user_id)
            elif callback_data == "profile_menu":
                handle_profile_menu(chat_id, message_id, user_id)
            elif callback_data == "add_profile":
                handle_add_profile(chat_id)
            elif callback_data == "back_menu":
                handle_back_menu(chat_id, message_id, user_id, user_name)
            elif callback_data == "view_stats":
                text = "📊 <b>Stats Coming Soon!</b>"
                keyboard = [
                    [{"text": "🔙 Back", "callback_data": "back_menu"}],
                ]
                edit_message(chat_id, message_id, text, keyboard)
        
        return "OK", 200
    
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "ERROR", 500

@app.route("/health", methods=["GET"])
def health():
    """Health check"""
    return "OK", 200

# ═══════════════════════════════════════════════════════════════════════
# 🚀 MAIN
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"🤖 Bot running on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)
