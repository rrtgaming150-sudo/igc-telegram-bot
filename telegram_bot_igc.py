#!/usr/bin/env python3
"""
🎯 COMPLETE IGC Bot
- Import JSON cache (answers + question IDs)
- Save profiles with cookies
- Show BEFORE/AFTER stats (rank, ELO, challenges)
- Run 3 parallel quiz attempts
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
import threading

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

def get_user_profiles(user_id):
    profiles = load_profiles()
    return profiles.get(str(user_id), {})

# ═══════════════════════════════════════════════════════════════════════
# 📱 TELEGRAM API HELPERS
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
    except:
        pass

# ═══════════════════════════════════════════════════════════════════════
# 🌐 API FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

async def fetch_stats(cookies):
    """Fetch: Rank, ELO Score, Challenges Completed"""
    try:
        async with aiohttp.ClientSession() as session:
            # Fetch from leaderboard API
            async with session.get(
                f"{BASE_URL}/api/leaderboard",
                cookies=cookies,
                timeout=aiohttp.ClientTimeout(total=8)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("success"):
                        stats_data = data.get("data", {})
                        return {
                            "rank": stats_data.get("rank"),
                            "eloScore": stats_data.get("eloScore"),
                            "totalChallenges": stats_data.get("totalChallenges"),
                            "attemptsLeft": stats_data.get("attemptsLeft", 0)
                        }
    except Exception as e:
        logger.error(f"Fetch stats error: {e}")
    return None

async def check_attempts(cookies):
    """Check attempts left"""
    try:
        stats = await fetch_stats(cookies)
        return stats.get("attemptsLeft", 0) if stats else 0
    except:
        return 0

async def generate_attempt(cookies, answers_cache):
    """Generate and answer a single attempt"""
    try:
        async with aiohttp.ClientSession() as session:
            # Generate attempt
            async with session.post(
                f"{BASE_URL}/api/attempt/generate",
                json={},
                cookies=cookies,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status not in (200, 201):
                    return None
                
                data = await resp.json()
                if not data.get("success"):
                    return None
                
                attempt = data.get("data", {})
                attempt_id = attempt.get("_id")
                questions = attempt.get("questions", [])
                
                correct_count = 0
                total_count = len(questions)
                
                # Answer each question
                for question in questions:
                    question_id = question.get("_id")
                    
                    # Get answer from cache
                    answer = answers_cache.get(question_id, "")
                    
                    if not answer:
                        continue
                    
                    # Submit answer
                    try:
                        body = {
                            "_id": attempt_id,
                            "questionId": question_id,
                            "question": "",
                            "selectedAnswer": answer,
                            "timeSpent": 3,
                        }
                        
                        async with session.post(
                            f"{BASE_URL}/api/attempt/validate",
                            json=body,
                            cookies=cookies,
                            timeout=aiohttp.ClientTimeout(total=10)
                        ) as v_resp:
                            if v_resp.status == 200:
                                v_data = await v_resp.json()
                                if v_data.get("success"):
                                    q_attempts = v_data.get("data", {}).get("QuestionsAttempted", [])
                                    if q_attempts and q_attempts[-1].get("isCorrect"):
                                        correct_count += 1
                        
                        await asyncio.sleep(0.5)
                    
                    except:
                        pass
                
                return {"correct": correct_count, "total": total_count}
    
    except Exception as e:
        logger.error(f"Generate attempt error: {e}")
    
    return None

async def run_parallel_attempts(cookies, answers_cache, num_attempts=3):
    """Run multiple attempts in parallel"""
    tasks = []
    for _ in range(num_attempts):
        tasks.append(generate_attempt(cookies, answers_cache))
    
    results = await asyncio.gather(*tasks)
    
    total_correct = sum(r["correct"] for r in results if r)
    total_questions = sum(r["total"] for r in results if r)
    
    return {
        "attempts": len([r for r in results if r]),
        "total_correct": total_correct,
        "total_questions": total_questions,
        "per_attempt": results
    }

# ═══════════════════════════════════════════════════════════════════════
# 🎯 MAIN HANDLERS
# ═══════════════════════════════════════════════════════════════════════

def main_menu(chat_id, user_name):
    """Main menu"""
    text = f"""
🎯 <b>INDIA GENIUS CHALLENGE BOT</b>

👋 Welcome, {user_name}!

Choose an option:
"""
    
    keyboard = [
        [{"text": "🎮 Start Quiz", "callback_data": "start_quiz"}],
        [{"text": "👤 Manage Profiles", "callback_data": "profiles"}],
        [{"text": "📝 Answer Cache", "callback_data": "cache"}],
        [{"text": "📊 View Stats", "callback_data": "stats"}],
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
        text += "No profiles yet. Create one to start!\n"
    
    keyboard = [
        [{"text": "➕ Add New Profile", "callback_data": "add_profile"}],
        [{"text": "🔙 Back", "callback_data": "back"}],
    ]
    
    if message_id:
        edit_message(chat_id, message_id, text, keyboard)
    else:
        send_message(chat_id, text, keyboard)

def show_cache(chat_id, message_id=None):
    """Show cache menu"""
    cache = load_cache()
    count = len(cache.get("answers", {}))
    
    text = f"""
📝 <b>Answer Cache</b>

📅 Date: {cache.get('date')}
📊 Total Answers: {count}

<b>JSON Format:</b>
{{"answers": {{"question_id": "answer"}}}}

Example:
{{"answers": {{"68edd617e496d06d1f48987a": "Polo"}}}}
"""
    
    keyboard = [
        [{"text": "📥 Import Cache JSON", "callback_data": "import_cache"}],
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
    """Handle webhook updates"""
    try:
        data = request.get_json()
        
        # ═══ MESSAGE ═══
        if "message" in data:
            msg = data["message"]
            chat_id = msg["chat"]["id"]
            user_id = msg["from"]["id"]
            user_name = msg["from"].get("first_name", "User")
            text = msg.get("text", "")
            
            state = get_user_state(user_id)
            
            if text == "/start":
                main_menu(chat_id, user_name)
            
            # Add Profile - Step 1: Name
            elif state.get("waiting_profile_name"):
                set_user_state(user_id, {
                    "waiting_token": True,
                    "profile_name": text
                })
                send_message(chat_id, 
                    "🔐 <b>Enter Session Token</b>\n\n"
                    "📍 Location: Browser → F12 → Cookies\n"
                    "🔑 Key: __Secure-better-auth.session_token\n\n"
                    "Just paste it here:")
            
            # Add Profile - Step 2: Token
            elif state.get("waiting_token"):
                set_user_state(user_id, {
                    "waiting_data": True,
                    "profile_name": state.get("profile_name"),
                    "session_token": text
                })
                send_message(chat_id,
                    "🔐 <b>Enter Session Data</b>\n\n"
                    "📍 Location: Browser → F12 → Cookies\n"
                    "🔑 Key: __Secure-better-auth.session_data\n\n"
                    "Just paste it here:")
            
            # Add Profile - Step 3: Data
            elif state.get("waiting_data"):
                profile_name = state.get("profile_name")
                token = state.get("session_token")
                session_data = text
                
                save_profile(user_id, profile_name, token, session_data)
                set_user_state(user_id, {})
                
                send_message(chat_id,
                    f"✅ <b>Profile Saved!</b>\n\n"
                    f"<code>{profile_name}</code>\n\n"
                    f"Send /start to continue")
            
            # Import Cache
            elif state.get("waiting_cache"):
                try:
                    cache_json = json.loads(text)
                    
                    if "answers" not in cache_json:
                        send_message(chat_id, 
                            "❌ <b>Invalid Format!</b>\n\n"
                            'Need: {"answers": {"id": "answer"}}')
                        return "OK", 200
                    
                    # Merge with existing cache
                    current_cache = load_cache()
                    current_cache["answers"].update(cache_json["answers"])
                    save_cache(current_cache)
                    
                    added = len(cache_json["answers"])
                    total = len(current_cache["answers"])
                    
                    send_message(chat_id,
                        f"✅ <b>Cache Imported!</b>\n\n"
                        f"Added: {added} answers\n"
                        f"Total: {total} answers\n\n"
                        f"Send /start to continue")
                    
                    set_user_state(user_id, {})
                
                except json.JSONDecodeError:
                    send_message(chat_id, "❌ <b>Invalid JSON!</b>\n\nCheck format and try again")
            
            else:
                send_message(chat_id, "Send /start to begin!")
        
        # ═══ CALLBACK ═══
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
                        [[{"text": "➕ Create Profile", "callback_data": "add_profile"}],
                         [{"text": "🔙 Back", "callback_data": "back"}]])
                    return "OK", 200
                
                # Select profile
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
            
            elif cb_data == "import_cache":
                set_user_state(user_id, {"waiting_cache": True})
                send_message(chat_id,
                    "📥 <b>Paste Your Cache JSON</b>\n\n"
                    '<b>Format:</b>\n{"answers": {"question_id": "answer"}}')
            
            elif cb_data == "back":
                main_menu(chat_id, user_name)
            
            elif cb_data.startswith("sel_"):
                profile_name = cb_data.replace("sel_", "")
                profiles = get_user_profiles(user_id)
                profile = profiles.get(profile_name)
                
                if not profile:
                    edit_message(chat_id, msg_id, "❌ Profile not found",
                        [[{"text": "🔙 Back", "callback_data": "back"}]])
                    return "OK", 200
                
                # Get cookies
                cookies = {
                    "__Secure-better-auth.session_token": profile["session_token"],
                    "__Secure-better-auth.session_data": profile["session_data"],
                }
                
                # Fetch BEFORE stats
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                stats_before = loop.run_until_complete(fetch_stats(cookies))
                loop.close()
                
                if not stats_before:
                    edit_message(chat_id, msg_id,
                        "❌ <b>Failed to fetch stats!</b>\n\nCheck cookies",
                        [[{"text": "🔙 Back", "callback_data": "back"}]])
                    return "OK", 200
                
                attempts = stats_before.get("attemptsLeft", 0)
                
                if attempts <= 0:
                    edit_message(chat_id, msg_id,
                        f"❌ <b>No Attempts Left!</b>\n\nAttempts: {attempts}\n\nCome back tomorrow!",
                        [[{"text": "🔙 Back", "callback_data": "back"}]])
                    return "OK", 200
                
                # Show BEFORE stats
                text = f"""
✅ <b>Profile Selected: {profile_name}</b>

📊 <b>BEFORE Stats:</b>
🏆 Rank: {stats_before.get('rank', 'N/A')}
⚡ ELO Score: {stats_before.get('eloScore', 'N/A')}
🎯 Challenges: {stats_before.get('totalChallenges', 'N/A')}
📋 Attempts Left: {attempts}

Ready to fire 3 attempts?
"""
                
                keyboard = [
                    [{"text": "▶️ Run Quiz", "callback_data": f"run_{profile_name}"}],
                    [{"text": "🔙 Back", "callback_data": "back"}],
                ]
                
                edit_message(chat_id, msg_id, text, keyboard)
                
                # Save state
                set_user_state(user_id, {
                    "selected_profile": profile_name,
                    "cookies": cookies,
                    "stats_before": stats_before
                })
            
            elif cb_data.startswith("run_"):
                state = get_user_state(user_id)
                cookies = state.get("cookies")
                stats_before = state.get("stats_before", {})
                
                if not cookies:
                    edit_message(chat_id, msg_id, "❌ Session expired",
                        [[{"text": "🔙 Back", "callback_data": "back"}]])
                    return "OK", 200
                
                # Update - Running
                edit_message(chat_id, msg_id,
                    "🚀 <b>Starting Quiz...</b>\n\n"
                    "⏳ Running 3 attempts...\n"
                    "⏱️ This will take ~20 seconds", None)
                
                # Run quiz in background
                def run_quiz():
                    try:
                        cache = load_cache()
                        answers_cache = cache.get("answers", {})
                        
                        # Run parallel attempts
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        quiz_result = loop.run_until_complete(
                            run_parallel_attempts(cookies, answers_cache, 3)
                        )
                        loop.close()
                        
                        # Fetch AFTER stats
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        stats_after = loop.run_until_complete(fetch_stats(cookies))
                        loop.close()
                        
                        # Calculate differences
                        rank_before = stats_before.get("rank", 0)
                        rank_after = stats_after.get("rank", 0) if stats_after else rank_before
                        rank_change = rank_before - rank_after  # Positive = improved
                        
                        elo_before = stats_before.get("eloScore", 0)
                        elo_after = stats_after.get("eloScore", 0) if stats_after else elo_before
                        elo_change = elo_after - elo_before
                        
                        challenges_before = stats_before.get("totalChallenges", 0)
                        challenges_after = stats_after.get("totalChallenges", 0) if stats_after else challenges_before
                        challenges_change = challenges_after - challenges_before
                        
                        # Format result
                        result_text = f"""
✅ <b>Quiz Complete!</b>

📊 <b>BEFORE Stats:</b>
🏆 Rank: {rank_before}
⚡ ELO: {elo_before}
🎯 Challenges: {challenges_before}

📊 <b>AFTER Stats:</b>
🏆 Rank: {rank_after} ({"↑" if rank_change > 0 else "↓"} {abs(rank_change)})
⚡ ELO: {elo_after} ({"+" if elo_change >= 0 else ""}{elo_change})
🎯 Challenges: {challenges_after} ({"+" if challenges_change >= 0 else ""}{challenges_change})

📈 <b>Quiz Results:</b>
✨ Correct: {quiz_result['total_correct']}/{quiz_result['total_questions']}
🎮 Attempts: {quiz_result['attempts']}/3
⏱️ Time: ~{20}s
"""
                        
                        edit_message(chat_id, msg_id, result_text,
                            [[{"text": "🔙 Back", "callback_data": "back"}]])
                    
                    except Exception as e:
                        logger.error(f"Quiz error: {e}")
                        edit_message(chat_id, msg_id,
                            f"❌ <b>Error:</b> {str(e)}",
                            [[{"text": "🔙 Back", "callback_data": "back"}]])
                
                # Run in thread
                thread = threading.Thread(target=run_quiz)
                thread.daemon = True
                thread.start()
            
            elif cb_data == "stats":
                profiles = get_user_profiles(user_id)
                
                if not profiles:
                    edit_message(chat_id, msg_id, "❌ No profiles",
                        [[{"text": "🔙 Back", "callback_data": "back"}]])
                    return "OK", 200
                
                text = "📊 <b>Select Profile:</b>"
                keyboard = []
                for name in profiles.keys():
                    keyboard.append([{"text": f"📊 {name}", "callback_data": f"stat_{name}"}])
                keyboard.append([{"text": "🔙 Back", "callback_data": "back"}])
                
                edit_message(chat_id, msg_id, text, keyboard)
            
            elif cb_data.startswith("stat_"):
                profile_name = cb_data.replace("stat_", "")
                profiles = get_user_profiles(user_id)
                profile = profiles.get(profile_name)
                
                if not profile:
                    edit_message(chat_id, msg_id, "❌ Not found",
                        [[{"text": "🔙 Back", "callback_data": "stats"}]])
                    return "OK", 200
                
                cookies = {
                    "__Secure-better-auth.session_token": profile["session_token"],
                    "__Secure-better-auth.session_data": profile["session_data"],
                }
                
                # Fetch stats
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                stats = loop.run_until_complete(fetch_stats(cookies))
                loop.close()
                
                text = f"""
📊 <b>Stats - {profile_name}</b>

🏆 Rank: {stats.get('rank', 'N/A') if stats else 'N/A'}
⚡ ELO Score: {stats.get('eloScore', 'N/A') if stats else 'N/A'}
🎯 Challenges: {stats.get('totalChallenges', 'N/A') if stats else 'N/A'}
📋 Attempts Left: {stats.get('attemptsLeft', 0) if stats else 0}
"""
                
                edit_message(chat_id, msg_id, text,
                    [[{"text": "🔙 Back", "callback_data": "stats"}]])
        
        return "OK", 200
    
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "ERROR", 500

@app.route("/setup", methods=["GET"])
def setup():
    """Setup webhook"""
    try:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        
        requests.get(f"{TELEGRAM_API}/deleteWebhook")
        response = requests.post(f"{TELEGRAM_API}/setWebhook",
            json={"url": webhook_url})
        
        if response.json().get("ok"):
            return f"✅ Webhook set: {webhook_url}", 200
        else:
            return f"❌ Failed", 500
    
    except Exception as e:
        return f"❌ Error: {str(e)}", 500

@app.route("/health", methods=["GET"])
def health():
    return "OK", 200

@app.route("/", methods=["GET"])
def index():
    return f"<h1>🤖 IGC Bot</h1><p><a href='/setup'>Setup</a></p>", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
