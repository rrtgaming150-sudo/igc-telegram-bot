#!/usr/bin/env python3
"""
🎯 India Genius Challenge - Telegram Bot
Run 3 parallel quiz attempts with answer caching and profile management
"""

import asyncio
import json
import os
import aiohttp
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes, CallbackQueryHandler,
    MessageHandler, ConversationHandler, filters
)
from telegram.constants import ParseMode, ChatAction

# ═══════════════════════════════════════════════════════════════════════
# 🔧 CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8989521653:AAGGnpq4bX_U4pQbTSjpdEZbjACUpD6jEnI")
BASE_URL = "https://www.indiageniuschallenge.com"
STORAGE_DIR = Path("data")
STORAGE_DIR.mkdir(exist_ok=True)

PROFILES_FILE = STORAGE_DIR / "profiles.json"
CACHE_FILE = STORAGE_DIR / "answers_cache.json"
STATS_FILE = STORAGE_DIR / "user_stats.json"

# Conversation states
(MAIN_MENU, ADDING_PROFILE, INPUT_SESSION_TOKEN, INPUT_SESSION_DATA,
 QUIZ_MENU, RUNNING_QUIZ, VIEWING_STATS) = range(7)

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

def load_cache() -> Dict:
    """Load answer cache"""
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except:
            return {}
    return {}

def save_cache(data: Dict) -> None:
    """Save answer cache"""
    CACHE_FILE.write_text(json.dumps(data, indent=2))

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

def delete_user_profile(user_id: int, profile_name: str) -> bool:
    """Delete a user profile"""
    profiles = load_profiles()
    user_id_str = str(user_id)
    if user_id_str in profiles and profile_name in profiles[user_id_str]:
        del profiles[user_id_str][profile_name]
        save_profiles(profiles)
        return True
    return False

# ═══════════════════════════════════════════════════════════════════════
# 🌐 API FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

async def fetch_leaderboard_stats(cookies: Dict) -> Optional[Dict]:
    """Fetch rank and challenges from /api/leaderboard"""
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
                        user_data = data.get("data", {})
                        return {
                            "rank": user_data.get("rank", 0),
                            "totalChallenges": user_data.get("totalChallenges", 0),
                        }
    except Exception as e:
        print(f"Leaderboard error: {e}")
    return None

async def fetch_elo_score(cookies: Dict) -> Optional[Dict]:
    """Fetch ELO score from /api/users/me"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{BASE_URL}/api/users/me",
                cookies=cookies,
                timeout=aiohttp.ClientTimeout(total=8),
                headers=HEADERS
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("success"):
                        user = data.get("data", {})
                        return {
                            "eloScore": user.get("eloScore", 0),
                            "totalAttempts": user.get("totalAttempts", 0),
                        }
    except Exception as e:
        print(f"ELO error: {e}")
    return None

async def check_attempts_left(cookies: Dict) -> Tuple[int, Optional[Dict]]:
    """Check if user has attempts left"""
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
                        stats = data.get("data", {})
                        return stats.get("attemptsLeft", 0), stats
    except:
        pass
    return 0, None

async def generate_attempt(cookies: Dict) -> Optional[Dict]:
    """Generate a new attempt"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{BASE_URL}/api/attempt/generate",
                json={},
                cookies=cookies,
                timeout=aiohttp.ClientTimeout(total=15),
                headers=HEADERS
            ) as resp:
                if resp.status in (200, 201):
                    data = await resp.json()
                    if data.get("success"):
                        return data.get("data")
    except Exception as e:
        print(f"Generate error: {e}")
    return None

async def answer_question(cookies: Dict, attempt_data: Dict, question_id: str, answer: str) -> bool:
    """Submit an answer"""
    try:
        body = {
            "_id": attempt_data.get("attempt", {}).get("_id"),
            "questionId": question_id,
            "question": "",
            "selectedAnswer": answer,
            "timeSpent": 3,
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{BASE_URL}/api/attempt/validate",
                json=body,
                cookies=cookies,
                timeout=aiohttp.ClientTimeout(total=10),
                headers=HEADERS
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("success"):
                        questions = data.get("data", {}).get("QuestionsAttempted", [])
                        if questions:
                            return questions[-1].get("isCorrect", False)
    except:
        pass
    return False

# ═══════════════════════════════════════════════════════════════════════
# 🤖 TELEGRAM HANDLERS
# ═══════════════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start command"""
    user_id = update.effective_user.id
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
        [InlineKeyboardButton("📝 Answer Cache", callback_data="cache_menu")],
    ]
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )
    
    return MAIN_MENU

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
                "Please create a profile first with your cookies.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Add Profile", callback_data="add_profile")],
                    [InlineKeyboardButton("🔙 Back", callback_data="back_menu")],
                ]),
                parse_mode=ParseMode.HTML
            )
            return MAIN_MENU
        
        # Show profiles to select
        keyboard = []
        for profile_name in profiles.keys():
            keyboard.append([InlineKeyboardButton(f"✅ {profile_name}", callback_data=f"select_profile_{profile_name}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_menu")])
        
        await query.edit_message_text(
            "📋 <b>Select a Profile:</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
        return QUIZ_MENU
    
    elif data == "profile_menu":
        profiles = get_user_profiles(user_id)
        
        text = "👤 <b>Profile Management</b>\n\n"
        if profiles:
            text += "<b>Your Profiles:</b>\n"
            for name in profiles.keys():
                text += f"  • {name}\n"
        else:
            text += "<i>No profiles yet</i>\n"
        
        keyboard = [
            [InlineKeyboardButton("➕ Add New Profile", callback_data="add_profile")],
        ]
        if profiles:
            keyboard.append([InlineKeyboardButton("🗑️ Delete Profile", callback_data="delete_profile")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_menu")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
        return MAIN_MENU
    
    elif data == "add_profile":
        await query.edit_message_text(
            "🔐 <b>Enter Profile Name</b>\n\n"
            "Type a unique name for this profile:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="back_menu")],
            ]),
            parse_mode=ParseMode.HTML
        )
        context.user_data["adding_profile"] = True
        return ADDING_PROFILE
    
    elif data == "back_menu":
        await start(update, context)
        return MAIN_MENU
    
    elif data.startswith("select_profile_"):
        profile_name = data.replace("select_profile_", "")
        profiles = get_user_profiles(user_id)
        profile = profiles.get(profile_name)
        
        if not profile:
            await query.answer("❌ Profile not found", show_alert=True)
            return QUIZ_MENU
        
        # Build cookies
        cookies = {
            "__Secure-better-auth.session_token": profile["session_token"],
            "__Secure-better-auth.session_data": profile["session_data"],
        }
        
        # Check attempts
        await query.edit_message_text(
            "⏳ <b>Checking attempts...</b>",
            parse_mode=ParseMode.HTML
        )
        
        attempts_left, stats = await check_attempts_left(cookies)
        
        if attempts_left <= 0:
            await query.edit_message_text(
                f"❌ <b>No Attempts Left!</b>\n\n"
                f"Come back tomorrow for a new challenge.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="back_menu")],
                ]),
                parse_mode=ParseMode.HTML
            )
            return MAIN_MENU
        
        # Store cookies for quiz
        context.user_data["cookies"] = cookies
        context.user_data["profile_name"] = profile_name
        
        await query.edit_message_text(
            f"✅ <b>Ready to Start!</b>\n\n"
            f"Profile: <code>{profile_name}</code>\n"
            f"Attempts Left: {attempts_left}\n\n"
            f"🎮 Ready to run 3 parallel attempts?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("▶️ Start Quiz", callback_data="run_quiz")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_menu")],
            ]),
            parse_mode=ParseMode.HTML
        )
        return QUIZ_MENU
    
    elif data == "run_quiz":
        cookies = context.user_data.get("cookies")
        if not cookies:
            await query.answer("❌ No profile selected", show_alert=True)
            return QUIZ_MENU
        
        await query.edit_message_text(
            "🚀 <b>Starting Quiz...</b>\n\n"
            "Generating 3 attempts...",
            parse_mode=ParseMode.HTML
        )
        
        context.user_data["quiz_message"] = query.message
        
        # Run quiz in background
        asyncio.create_task(run_quiz_parallel(context, cookies, query))
        return RUNNING_QUIZ
    
    elif data == "view_stats":
        profiles = get_user_profiles(user_id)
        
        if not profiles:
            await query.edit_message_text(
                "❌ No profiles to check stats",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="back_menu")],
                ]),
                parse_mode=ParseMode.HTML
            )
            return MAIN_MENU
        
        # Show profile selection for stats
        keyboard = []
        for profile_name in profiles.keys():
            keyboard.append([InlineKeyboardButton(f"📊 {profile_name}", callback_data=f"stats_{profile_name}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_menu")])
        
        await query.edit_message_text(
            "📊 <b>Select Profile for Stats:</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
        return VIEWING_STATS
    
    elif data.startswith("stats_"):
        profile_name = data.replace("stats_", "")
        profiles = get_user_profiles(user_id)
        profile = profiles.get(profile_name)
        
        if not profile:
            await query.answer("❌ Profile not found", show_alert=True)
            return VIEWING_STATS
        
        cookies = {
            "__Secure-better-auth.session_token": profile["session_token"],
            "__Secure-better-auth.session_data": profile["session_data"],
        }
        
        # Fetch stats
        leaderboard = await fetch_leaderboard_stats(cookies)
        elo = await fetch_elo_score(cookies)
        
        text = f"📊 <b>Stats for {profile_name}</b>\n\n"
        
        if leaderboard:
            text += f"🏆 <b>Rank:</b> {leaderboard.get('rank', 'N/A')}\n"
            text += f"🎯 <b>Challenges:</b> {leaderboard.get('totalChallenges', 'N/A')}\n"
        
        if elo:
            text += f"⚡ <b>ELO Score:</b> {elo.get('eloScore', 'N/A')}\n"
            text += f"📈 <b>Total Attempts:</b> {elo.get('totalAttempts', 'N/A')}\n"
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="view_stats")],
            ]),
            parse_mode=ParseMode.HTML
        )
        return VIEWING_STATS
    
    elif data == "cache_menu":
        cache = load_cache()
        cache_date = cache.get("date", "Unknown")
        cache_count = len(cache.get("answers", {}))
        
        text = f"""
📝 <b>Answer Cache</b>

📅 Date: {cache_date}
📊 Cached Answers: {cache_count}

What would you like to do?
"""
        
        keyboard = [
            [InlineKeyboardButton("➕ Add Answers", callback_data="add_cache")],
            [InlineKeyboardButton("📥 Import Cache", callback_data="import_cache")],
            [InlineKeyboardButton("📤 Export Cache", callback_data="export_cache")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_menu")],
        ]
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
        return MAIN_MENU
    
    return MAIN_MENU

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle text messages"""
    text = update.message.text.strip()
    
    if context.user_data.get("adding_profile"):
        context.user_data["profile_name"] = text
        context.user_data["adding_profile"] = False
        
        await update.message.reply_text(
            "🔐 <b>Enter Session Token</b>\n\n"
            "Copy from: Browser DevTools → Cookies → __Secure-better-auth.session_token",
            parse_mode=ParseMode.HTML
        )
        return INPUT_SESSION_TOKEN
    
    elif context.user_data.get("waiting_token"):
        context.user_data["session_token"] = text
        context.user_data["waiting_token"] = False
        
        await update.message.reply_text(
            "🔐 <b>Enter Session Data</b>\n\n"
            "Copy from: Browser DevTools → Cookies → __Secure-better-auth.session_data",
            parse_mode=ParseMode.HTML
        )
        return INPUT_SESSION_DATA
    
    elif context.user_data.get("waiting_data"):
        context.user_data["session_data"] = text
        context.user_data["waiting_data"] = False
        
        # Save profile
        user_id = update.effective_user.id
        profile_name = context.user_data.get("profile_name", "Default")
        session_token = context.user_data.get("session_token")
        session_data = context.user_data.get("session_data")
        
        save_user_profile(user_id, profile_name, session_token, session_data)
        
        await update.message.reply_text(
            f"✅ <b>Profile Saved!</b>\n\n"
            f"Profile: <code>{profile_name}</code>\n\n"
            f"You can now use this profile to run quizzes.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎮 Start Quiz", callback_data="quiz_menu")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_menu")],
            ]),
            parse_mode=ParseMode.HTML
        )
        return MAIN_MENU
    
    return MAIN_MENU

async def run_quiz_parallel(context: ContextTypes.DEFAULT_TYPE, cookies: Dict, query) -> None:
    """Run 3 parallel quiz attempts"""
    try:
        # Generate 3 attempts
        attempts = []
        for i in range(3):
            attempt_data = await generate_attempt(cookies)
            if attempt_data:
                attempts.append({
                    "num": i + 1,
                    "data": attempt_data,
                    "correct": 0,
                })
        
        if not attempts:
            await query.edit_message_text(
                "❌ <b>Error</b>\n\nCould not generate attempts",
                parse_mode=ParseMode.HTML
            )
            return
        
        # Get answers from cache
        cache = load_cache()
        answers = cache.get("answers", {})
        
        # Answer questions
        max_questions = 15
        total_correct = 0
        
        for q_idx in range(max_questions):
            for att in attempts:
                questions = att["data"].get("quiz", {}).get("Questions", [])
                if q_idx < len(questions):
                    question = questions[q_idx]
                    question_id = question["_id"]
                    answer = answers.get(question_id, "")
                    
                    if answer:
                        is_correct = await answer_question(cookies, att["data"], question_id, answer)
                        if is_correct:
                            att["correct"] += 1
                            total_correct += 1
            
            # Update progress
            progress_text = f"""
🚀 <b>Running Quiz...</b>

Question: {q_idx + 1}/{max_questions}

Attempts Progress:
"""
            for att in attempts:
                progress_text += f"  Attempt {att['num']}: {att['correct']} ✅\n"
            
            try:
                await query.edit_message_text(
                    progress_text,
                    parse_mode=ParseMode.HTML
                )
            except:
                pass
            
            await asyncio.sleep(0.8)
        
        # Final summary
        summary = f"""
✅ <b>Quiz Complete!</b>

📊 <b>Results:</b>
"""
        for att in attempts:
            summary += f"  Attempt {att['num']}: {att['correct']}/15 ✅\n"
        
        summary += f"\n🎯 <b>Total Correct:</b> {total_correct}/45"
        
        await query.edit_message_text(
            summary,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="back_menu")],
            ]),
            parse_mode=ParseMode.HTML
        )
    
    except Exception as e:
        await query.edit_message_text(
            f"❌ <b>Error</b>\n\n{str(e)[:100]}",
            parse_mode=ParseMode.HTML
        )

def main():
    """Start the bot"""
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        message_handler
    ))
    
    print("🤖 Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
