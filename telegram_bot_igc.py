#!/usr/bin/env python3
"""
🎯 India Genius Challenge - Telegram Bot (Fixed Version)
Python 3.11+ Compatible
"""

import asyncio
import json
import os
import logging
from pathlib import Path
from datetime import datetime
import aiohttp
from typing import Dict, Optional, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes, CallbackQueryHandler,
    MessageHandler, filters
)
from telegram.constants import ParseMode

# ═══════════════════════════════════════════════════════════════════════
# 🔧 CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8989521653:AAGGnpq4bX_U4pQbTSjpdEZbjACUpD6jEnI")
BASE_URL = "https://www.indiageniuschallenge.com"
STORAGE_DIR = Path("data")
STORAGE_DIR.mkdir(exist_ok=True)

PROFILES_FILE = STORAGE_DIR / "profiles.json"
CACHE_FILE = STORAGE_DIR / "answers_cache.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36"
}

# ═══════════════════════════════════════════════════════════════════════
# 💾 STORAGE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def load_profiles() -> Dict:
    """Load all user profiles"""
    if PROFILES_FILE.exists():
        try:
            return json.loads(PROFILES_FILE.read_text())
        except:
            return {}
    return {}

def save_profiles(data: Dict) -> None:
    """Save all profiles"""
    PROFILES_FILE.write_text(json.dumps(data, indent=2))

def get_user_profiles(user_id: int) -> Dict:
    """Get profiles for a user"""
    profiles = load_profiles()
    return profiles.get(str(user_id), {})

def save_user_profile(user_id: int, profile_name: str, session_token: str, session_data: str) -> None:
    """Save a user profile"""
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
# 🌐 API FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

async def fetch_stats(cookies: Dict) -> Optional[Dict]:
    """Fetch user stats"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{BASE_URL}/api/leaderboard",
                cookies=cookies,
                timeout=aiohttp.ClientTimeout(total=8),
                headers=HEADERS
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("success"):
                        return data.get("data", {})
    except Exception as e:
        logger.error(f"Stats fetch error: {e}")
    return None

async def check_attempts(cookies: Dict) -> int:
    """Check attempts left"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{BASE_URL}/api/user/stats",
                cookies=cookies,
                timeout=aiohttp.ClientTimeout(total=8),
                headers=HEADERS
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("success"):
                        return data.get("data", {}).get("attemptsLeft", 0)
    except:
        pass
    return 0

# ═══════════════════════════════════════════════════════════════════════
# 🤖 TELEGRAM HANDLERS
# ═══════════════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start command"""
    user_name = update.effective_user.first_name
    
    text = f"""
╔══════════════════════════════════════╗
║ 🎯 INDIA GENIUS CHALLENGE - BOT 🎯  ║
║  Run 3 Parallel Quiz Attempts       ║
╚══════════════════════════════════════╝

👋 Welcome, {user_name}!

Choose what you'd like to do:
"""
    
    keyboard = [
        [InlineKeyboardButton("🎮 Start Quiz", callback_data="quiz_menu")],
        [InlineKeyboardButton("👤 Manage Profiles", callback_data="profile_menu")],
        [InlineKeyboardButton("📊 View Stats", callback_data="view_stats")],
    ]
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button clicks"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "quiz_menu":
        profiles = get_user_profiles(user_id)
        
        if not profiles:
            await query.edit_message_text(
                "❌ <b>No Profiles Found!</b>\n\n"
                "Please create a profile first.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Add Profile", callback_data="add_profile")],
                    [InlineKeyboardButton("🔙 Back", callback_data="back_menu")],
                ]),
                parse_mode=ParseMode.HTML
            )
            return
        
        keyboard = []
        for profile_name in profiles.keys():
            keyboard.append([InlineKeyboardButton(f"✅ {profile_name}", callback_data=f"select_{profile_name}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_menu")])
        
        await query.edit_message_text(
            "📋 <b>Select Profile:</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
    
    elif data == "profile_menu":
        profiles = get_user_profiles(user_id)
        
        text = "👤 <b>Profiles</b>\n\n"
        if profiles:
            for name in profiles.keys():
                text += f"  • {name}\n"
        else:
            text += "<i>No profiles</i>\n"
        
        keyboard = [
            [InlineKeyboardButton("➕ Add Profile", callback_data="add_profile")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_menu")],
        ]
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
    
    elif data == "add_profile":
        await query.edit_message_text(
            "📝 <b>Enter Profile Name</b>\n\n"
            "Send the profile name (e.g., MainAccount):",
            parse_mode=ParseMode.HTML
        )
        context.user_data["adding_profile"] = True
    
    elif data == "view_stats":
        profiles = get_user_profiles(user_id)
        
        if not profiles:
            await query.edit_message_text(
                "❌ No profiles",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="back_menu")],
                ]),
            )
            return
        
        keyboard = []
        for profile_name in profiles.keys():
            keyboard.append([InlineKeyboardButton(f"📊 {profile_name}", callback_data=f"stat_{profile_name}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_menu")])
        
        await query.edit_message_text(
            "📊 <b>Select Profile:</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
    
    elif data.startswith("stat_"):
        profile_name = data.replace("stat_", "")
        profiles = get_user_profiles(user_id)
        profile = profiles.get(profile_name)
        
        if not profile:
            await query.answer("❌ Profile not found", show_alert=True)
            return
        
        cookies = {
            "__Secure-better-auth.session_token": profile["session_token"],
            "__Secure-better-auth.session_data": profile["session_data"],
        }
        
        stats = await fetch_stats(cookies)
        
        if stats:
            text = f"""
📊 <b>Stats - {profile_name}</b>

🏆 Rank: {stats.get('rank', 'N/A')}
🎯 Challenges: {stats.get('totalChallenges', 'N/A')}
⚡ ELO: {stats.get('eloScore', 'N/A')}
"""
        else:
            text = "❌ Could not fetch stats"
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="view_stats")],
            ]),
            parse_mode=ParseMode.HTML
        )
    
    elif data == "back_menu":
        await start(update, context)
    
    elif data.startswith("select_"):
        profile_name = data.replace("select_", "")
        profiles = get_user_profiles(user_id)
        profile = profiles.get(profile_name)
        
        if not profile:
            await query.answer("❌ Profile not found", show_alert=True)
            return
        
        cookies = {
            "__Secure-better-auth.session_token": profile["session_token"],
            "__Secure-better-auth.session_data": profile["session_data"],
        }
        
        attempts = await check_attempts(cookies)
        
        if attempts <= 0:
            await query.edit_message_text(
                f"❌ <b>No Attempts Left!</b>\n\n"
                f"Come back tomorrow!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="back_menu")],
                ]),
                parse_mode=ParseMode.HTML
            )
            return
        
        await query.edit_message_text(
            f"✅ <b>Ready!</b>\n\n"
            f"Profile: {profile_name}\n"
            f"Attempts: {attempts}\n\n"
            f"🎮 Start Quiz?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("▶️ Start", callback_data="run_quiz")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_menu")],
            ]),
            parse_mode=ParseMode.HTML
        )
        context.user_data["selected_profile"] = profile_name
        context.user_data["cookies"] = cookies
    
    elif data == "run_quiz":
        await query.edit_message_text(
            "🚀 <b>Starting Quiz...</b>\n\n"
            "⏳ Running 3 attempts...",
            parse_mode=ParseMode.HTML
        )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages"""
    text = update.message.text.strip()
    
    if context.user_data.get("adding_profile"):
        context.user_data["profile_name"] = text
        context.user_data["adding_profile"] = False
        context.user_data["waiting_token"] = True
        
        await update.message.reply_text(
            "🔐 <b>Enter Session Token</b>\n\n"
            "From: Browser → F12 → Cookies → __Secure-better-auth.session_token",
            parse_mode=ParseMode.HTML
        )
    
    elif context.user_data.get("waiting_token"):
        context.user_data["session_token"] = text
        context.user_data["waiting_token"] = False
        context.user_data["waiting_data"] = True
        
        await update.message.reply_text(
            "🔐 <b>Enter Session Data</b>\n\n"
            "From: Browser → F12 → Cookies → __Secure-better-auth.session_data",
            parse_mode=ParseMode.HTML
        )
    
    elif context.user_data.get("waiting_data"):
        user_id = update.effective_user.id
        profile_name = context.user_data.get("profile_name", "Default")
        token = context.user_data.get("session_token")
        data = text
        
        save_user_profile(user_id, profile_name, token, data)
        
        context.user_data["waiting_data"] = False
        
        await update.message.reply_text(
            f"✅ <b>Profile Saved!</b>\n\n"
            f"{profile_name}\n\n"
            f"Use /start to begin",
            parse_mode=ParseMode.HTML
        )

def main() -> None:
    """Start the bot"""
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN":
        logger.error("❌ BOT_TOKEN not set!")
        return
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    logger.info("🤖 Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
