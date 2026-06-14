#!/usr/bin/env python3
"""
🎯 INDIA GENIUS CHALLENGE - COMPLETE TELEGRAM BOT (FIXED)
- File upload support for JSON (cookies & answers)
- Profile management
- 3 parallel attempts with BEFORE/AFTER stats
"""

import os
import json
import logging
import asyncio
import aiohttp
import re
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

def clear_user_state(user_id):
    states = load_user_state()
    if str(user_id) in states:
        del states[str(user_id)]
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

def delete_profile(user_id, profile_name):
    profiles = load_profiles()
    user_id_str = str(user_id)
    if user_id_str in profiles and profile_name in profiles[user_id_str]:
        del profiles[user_id_str][profile_name]
        save_profiles(profiles)
        return True
    return False

_active_profile = {}

def get_active_profile(user_id):
    profiles = get_user_profiles(user_id)
    if not profiles:
        return None, None
    nickname = _active_profile.get(user_id) or next(iter(profiles))
    if nickname not in profiles:
        nickname = next(iter(profiles))
    _active_profile[user_id] = nickname
    return nickname, profiles[nickname]

def set_active_profile(user_id, nickname):
    _active_profile[user_id] = nickname

# ═══════════════════════════════════════════════════════════════════════
# 📱 TELEGRAM API
# ═══════════════════════════════════════════════════════════════════════

def send_message(chat_id, text, keyboard=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if keyboard:
        data["reply_markup"] = {"inline_keyboard": keyboard}
    try:
        return requests.post(f"{TELEGRAM_API}/sendMessage", json=data, timeout=10).json()
    except Exception as e:
        logger.error(f"Send error: {e}")
        return None

def edit_message(chat_id, message_id, text, keyboard=None):
    data = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
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
# 🌐 API & STATS - FIXED TO HANDLE NONE VALUES
# ═══════════════════════════════════════════════════════════════════════

async def fetch_stats(cookies):
    """Fetch stats with proper None handling"""
    cookie_dict = {
        "__Secure-better-auth.session_token": cookies.get("session_token", ""),
        "__Secure-better-auth.session_data": cookies.get("session_data", ""),
    }
    
    # Default values (never None)
    stats = {
        "rank": 0,
        "eloScore": 0,
        "totalChallenges": 0,
        "attemptsLeft": 0
    }
    
    async with aiohttp.ClientSession() as session:
        # Try dashboard HTML parsing
        try:
            async with session.get(f"{BASE_URL}/dashboard", cookies=cookie_dict, timeout=10) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    
                    # Parse Rank
                    rank_match = re.search(r'Rank[:\s]*([\d,]+)\s*/\s*[\d,]+', html, re.IGNORECASE)
                    if rank_match:
                        stats["rank"] = int(rank_match.group(1).replace(",", ""))
                    
                    # Parse ELO/GP
                    gp_match = re.search(r'(?:GP|ELO|Score)[:\s]*([\d,]+)', html, re.IGNORECASE)
                    if gp_match:
                        stats["eloScore"] = int(gp_match.group(1).replace(",", ""))
                    
                    # Parse Challenges
                    chall_match = re.search(r'(?:Challenge|Played)[:\s]*([\d,]+)', html, re.IGNORECASE)
                    if chall_match:
                        stats["totalChallenges"] = int(chall_match.group(1).replace(",", ""))
        except Exception as e:
            logger.error(f"Dashboard parse error: {e}")
        
        # Try API endpoint
        try:
            async with session.get(f"{BASE_URL}/api/leaderboard", cookies=cookie_dict, timeout=8) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("success"):
                        board = data.get("data", {})
                        stats["rank"] = stats["rank"] or board.get("rank") or board.get("userRank") or 0
                        stats["totalChallenges"] = stats["totalChallenges"] or board.get("totalChallenges") or board.get("totalPlayed") or 0
                        stats["eloScore"] = stats["eloScore"] or board.get("eloScore") or 0
        except:
            pass
    
    # Ensure no None values
    stats["rank"] = stats["rank"] or 0
    stats["eloScore"] = stats["eloScore"] or 0
    stats["totalChallenges"] = stats["totalChallenges"] or 0
    stats["attemptsLeft"] = stats["attemptsLeft"] or 0
    
    return stats

async def generate_attempt(cookies, answers_cache):
    """Generate and answer a single attempt"""
    cookie_dict = {
        "__Secure-better-auth.session_token": cookies.get("session_token", ""),
        "__Secure-better-auth.session_data": cookies.get("session_data", ""),
    }
    try:
        async with aiohttp.ClientSession() as session:
            # Generate attempt
            async with session.post(f"{BASE_URL}/api/attempt/generate", json={}, cookies=cookie_dict, timeout=15) as resp:
                if resp.status not in (200, 201):
                    return None
                data = await resp.json()
                if not data.get("success"):
                    return None
                
                attempt = data.get("data", {})
                attempt_id = attempt.get("_id")
                questions = attempt.get("questions", [])
                correct = 0
                total = len(questions)
                
                # Answer each question
                for q in questions:
                    qid = q.get("_id")
                    ans = answers_cache.get(qid)
                    if not ans:
                        continue
                    
                    body = {
                        "_id": attempt_id,
                        "questionId": qid,
                        "question": "",
                        "selectedAnswer": ans,
                        "timeSpent": 3,
                    }
                    
                    try:
                        async with session.post(f"{BASE_URL}/api/attempt/validate", json=body, cookies=cookie_dict, timeout=10) as v_resp:
                            if v_resp.status == 200:
                                v_data = await v_resp.json()
                                if v_data.get("success"):
                                    attempted = v_data.get("data", {}).get("QuestionsAttempted", [])
                                    if attempted and attempted[-1].get("isCorrect"):
                                        correct += 1
                        await asyncio.sleep(0.5)
                    except:
                        pass
                
                return {"correct": correct, "total": total, "id": attempt_id}
    except Exception as e:
        logger.error(f"Generate attempt error: {e}")
    
    return None

async def run_parallel_attempts(cookies, answers_cache, n=3):
    """Run multiple attempts in parallel"""
    tasks = [generate_attempt(cookies, answers_cache) for _ in range(n)]
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
# 🎯 HANDLERS
# ═══════════════════════════════════════════════════════════════════════

def main_menu(chat_id, user_name):
    text = f"🎯 <b>INDIA GENIUS CHALLENGE BOT</b>\n\n👋 Welcome, {user_name}!\n\nChoose an option:"
    keyboard = [
        [{"text": "🎮 Start Quiz", "callback_data": "start_quiz"}],
        [{"text": "👤 Manage Profiles", "callback_data": "profiles"}],
        [{"text": "📝 Answer Cache", "callback_data": "cache"}],
        [{"text": "📊 View Stats", "callback_data": "stats"}],
    ]
    send_message(chat_id, text, keyboard)

def show_profiles(chat_id, user_id, message_id=None):
    profiles = get_user_profiles(user_id)
    text = "👤 <b>Your Profiles</b>\n\n"
    if profiles:
        for name in profiles.keys():
            active, _ = get_active_profile(user_id)
            marker = " ✅" if name == active else ""
            text += f"  • {name}{marker}\n"
    else:
        text += "No profiles yet.\n"
    keyboard = [[{"text": "➕ Add New Profile", "callback_data": "add_profile"}]]
    if profiles:
        keyboard.append([{"text": "🗑️ Delete Profile", "callback_data": "delete_profile"}])
    keyboard.append([{"text": "🔙 Back", "callback_data": "back"}])
    if message_id:
        edit_message(chat_id, message_id, text, keyboard)
    else:
        send_message(chat_id, text, keyboard)

def show_cache(chat_id, message_id=None):
    cache = load_cache()
    count = len(cache.get("answers", {}))
    text = f"📝 <b>Answer Cache</b>\n\n📅 Date: {cache.get('date')}\n📊 Answers: {count}\n\n<b>Send JSON file or paste:</b>\n{'{\"answers\": {\"id\": \"answer\"}}'}\nor\n[{'{\"question_id\": \"...\", \"correct_answer\": \"...\"}'}}]"
    keyboard = [[{"text": "🔙 Back", "callback_data": "back"}]]
    if message_id:
        edit_message(chat_id, message_id, text, keyboard)
    else:
        send_message(chat_id, text, keyboard)

# ═══════════════════════════════════════════════════════════════════════
# 🛠 FILE HANDLERS
# ═══════════════════════════════════════════════════════════════════════

def is_cookie_file(json_data):
    """Check if JSON is cookie format"""
    if isinstance(json_data, list):
        for item in json_data:
            if isinstance(item, dict):
                name = item.get("name")
                if name in ("__Secure-better-auth.session_token", "__Secure-better-auth.session_data"):
                    return True
    elif isinstance(json_data, dict):
        if "__Secure-better-auth.session_token" in json_data or "__Secure-better-auth.session_data" in json_data:
            return True
        if "session_token" in json_data and "session_data" in json_data:
            return True
    return False

def parse_cookie_json(data):
    """Parse cookie JSON to extract tokens"""
    if isinstance(data, list):
        cookies = {}
        for item in data:
            if item.get("name") == "__Secure-better-auth.session_token":
                cookies["session_token"] = item.get("value")
            elif item.get("name") == "__Secure-better-auth.session_data":
                cookies["session_data"] = item.get("value")
        if cookies.get("session_token") and cookies.get("session_data"):
            return cookies
    elif isinstance(data, dict):
        token = data.get("session_token") or data.get("__Secure-better-auth.session_token")
        session_data = data.get("session_data") or data.get("__Secure-better-auth.session_data")
        if token and session_data:
            return {"session_token": token, "session_data": session_data}
    return None

# ═══════════════════════════════════════════════════════════════════════
# 🌐 WEBHOOK
# ═══════════════════════════════════════════════════════════════════════

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        
        if "message" in data:
            msg = data["message"]
            chat_id = msg["chat"]["id"]
            user_id = msg["from"]["id"]
            user_name = msg["from"].get("first_name", "User")
            text = msg.get("text", "")
            state = get_user_state(user_id)

            # Handle JSON file uploads
            if "document" in msg:
                doc = msg["document"]
                if doc["file_name"].endswith(".json"):
                    file_info = requests.get(f"{TELEGRAM_API}/getFile?file_id={doc['file_id']}").json()
                    if not file_info.get("ok"):
                        send_message(chat_id, "❌ Failed to get file.")
                        return "OK", 200
                    
                    file_path = file_info["result"]["file_path"]
                    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
                    
                    try:
                        file_content = requests.get(file_url).text
                        json_data = json.loads(file_content)
                    except Exception as e:
                        send_message(chat_id, f"❌ Error reading file: {e}")
                        return "OK", 200

                    # Check if cookie file
                    if is_cookie_file(json_data):
                        if state.get("waiting_profile_data"):
                            name = state.get("profile_name")
                        else:
                            set_user_state(user_id, {"waiting_profile_name": True, "pending_cookie_data": json_data})
                            send_message(chat_id, "📝 Enter profile name for these cookies:")
                            return "OK", 200
                        
                        cookies = parse_cookie_json(json_data)
                        if cookies:
                            save_profile(user_id, name, cookies["session_token"], cookies["session_data"])
                            set_active_profile(user_id, name)
                            clear_user_state(user_id)
                            send_message(chat_id, f"✅ Profile <code>{name}</code> saved!")
                        else:
                            send_message(chat_id, "❌ Invalid cookie file.")
                    else:
                        # Answer cache file
                        if "answers" in json_data and isinstance(json_data["answers"], dict):
                            cur = load_cache()
                            cur["answers"].update(json_data["answers"])
                            save_cache(cur)
                            send_message(chat_id, f"✅ Imported {len(json_data['answers'])} answers. Total: {len(cur['answers'])}")
                            clear_user_state(user_id)
                        elif isinstance(json_data, list):
                            new_answers = {}
                            for item in json_data:
                                qid = item.get("question_id")
                                ans = item.get("correct_answer")
                                if qid and ans:
                                    new_answers[qid] = ans
                            if new_answers:
                                cur = load_cache()
                                cur["answers"].update(new_answers)
                                save_cache(cur)
                                send_message(chat_id, f"✅ Imported {len(new_answers)} answers. Total: {len(cur['answers'])}")
                                clear_user_state(user_id)
                            else:
                                send_message(chat_id, "❌ Array format invalid.")
                        else:
                            send_message(chat_id, "❌ Invalid format.")
                    
                    return "OK", 200

            # Handle text messages
            if text == "/start":
                main_menu(chat_id, user_name)
            elif state.get("waiting_profile_name"):
                if "pending_cookie_data" in state:
                    pending_json = state["pending_cookie_data"]
                    cookies = parse_cookie_json(pending_json)
                    if cookies:
                        save_profile(user_id, text, cookies["session_token"], cookies["session_data"])
                        set_active_profile(user_id, text)
                        clear_user_state(user_id)
                        send_message(chat_id, f"✅ Profile <code>{text}</code> saved!")
                    else:
                        send_message(chat_id, "❌ Invalid cookies.")
                else:
                    set_user_state(user_id, {"waiting_profile_data": True, "profile_name": text})
                    send_message(chat_id, "📄 Send cookie JSON file or paste JSON now.")
            elif state.get("waiting_profile_data") and text:
                try:
                    json_data = json.loads(text)
                    cookies = parse_cookie_json(json_data)
                    if cookies:
                        name = state["profile_name"]
                        save_profile(user_id, name, cookies["session_token"], cookies["session_data"])
                        set_active_profile(user_id, name)
                        clear_user_state(user_id)
                        send_message(chat_id, f"✅ Profile <code>{name}</code> saved!")
                    else:
                        send_message(chat_id, "❌ Invalid JSON format.")
                except:
                    send_message(chat_id, "❌ Invalid JSON.")
            elif state.get("waiting_cache") and text:
                try:
                    json_data = json.loads(text)
                    if "answers" in json_data and isinstance(json_data["answers"], dict):
                        cur = load_cache()
                        cur["answers"].update(json_data["answers"])
                        save_cache(cur)
                        send_message(chat_id, f"✅ Imported {len(json_data['answers'])} answers. Total: {len(cur['answers'])}")
                        clear_user_state(user_id)
                    elif isinstance(json_data, list):
                        new_answers = {}
                        for item in json_data:
                            qid = item.get("question_id")
                            ans = item.get("correct_answer")
                            if qid and ans:
                                new_answers[qid] = ans
                        if new_answers:
                            cur = load_cache()
                            cur["answers"].update(new_answers)
                            save_cache(cur)
                            send_message(chat_id, f"✅ Imported {len(new_answers)} answers. Total: {len(cur['answers'])}")
                            clear_user_state(user_id)
                        else:
                            send_message(chat_id, "❌ Array format invalid.")
                    else:
                        send_message(chat_id, "❌ Invalid format.")
                except Exception as e:
                    send_message(chat_id, f"❌ Invalid JSON: {e}")
            else:
                send_message(chat_id, "Send /start to begin.")

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
                    edit_message(chat_id, msg_id, "❌ No profiles. Create one first.",
                                 [[{"text": "➕ Add Profile", "callback_data": "add_profile"}], [{"text": "🔙 Back", "callback_data": "back"}]])
                    return "OK", 200
                text = "📋 Select profile:"
                keyboard = [[{"text": f"✅ {name}", "callback_data": f"sel_{name}"}] for name in profiles]
                keyboard.append([{"text": "🔙 Back", "callback_data": "back"}])
                edit_message(chat_id, msg_id, text, keyboard)

            elif cb_data == "profiles":
                show_profiles(chat_id, user_id, msg_id)
            elif cb_data == "add_profile":
                set_user_state(user_id, {"waiting_profile_name": True})
                edit_message(chat_id, msg_id, "📝 Enter profile name:", [[{"text": "❌ Cancel", "callback_data": "back"}]])
            elif cb_data == "delete_profile":
                profiles = get_user_profiles(user_id)
                text = "🗑️ Select to delete:"
                keyboard = [[{"text": f"❌ {name}", "callback_data": f"del_{name}"}] for name in profiles]
                keyboard.append([{"text": "🔙 Back", "callback_data": "back"}])
                edit_message(chat_id, msg_id, text, keyboard)
            elif cb_data.startswith("del_"):
                name = cb_data.replace("del_", "")
                if delete_profile(user_id, name):
                    edit_message(chat_id, msg_id, f"✅ Deleted {name}", [[{"text": "🔙 Profiles", "callback_data": "profiles"}]])
                else:
                    edit_message(chat_id, msg_id, "❌ Not found", [[{"text": "🔙 Back", "callback_data": "profiles"}]])
            elif cb_data == "cache":
                show_cache(chat_id, msg_id)
            elif cb_data == "import_cache":
                set_user_state(user_id, {"waiting_cache": True})
                edit_message(chat_id, msg_id, "📥 Send JSON file or paste:", [[{"text": "❌ Cancel", "callback_data": "back"}]])
            elif cb_data == "stats":
                profiles = get_user_profiles(user_id)
                if not profiles:
                    edit_message(chat_id, msg_id, "❌ No profiles.", [[{"text": "🔙 Back", "callback_data": "back"}]])
                    return "OK", 200
                text = "📊 Select profile:"
                keyboard = [[{"text": f"📊 {name}", "callback_data": f"stat_{name}"}] for name in profiles]
                keyboard.append([{"text": "🔙 Back", "callback_data": "back"}])
                edit_message(chat_id, msg_id, text, keyboard)
            elif cb_data.startswith("stat_"):
                name = cb_data.replace("stat_", "")
                profiles = get_user_profiles(user_id)
                profile = profiles.get(name)
                if not profile:
                    edit_message(chat_id, msg_id, "❌ Not found", [[{"text": "🔙 Back", "callback_data": "stats"}]])
                    return "OK", 200
                cookies = {"session_token": profile["session_token"], "session_data": profile["session_data"]}
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                stats = loop.run_until_complete(fetch_stats(cookies))
                loop.close()
                text = f"📊 <b>Stats - {name}</b>\n\n🏆 Rank: {stats.get('rank', 0) or 'N/A'}\n⚡ ELO: {stats.get('eloScore', 0) or 'N/A'}\n🎯 Challenges: {stats.get('totalChallenges', 0) or 'N/A'}\n📋 Attempts: {stats.get('attemptsLeft', 0) or 'N/A'}"
                edit_message(chat_id, msg_id, text, [[{"text": "🔙 Back", "callback_data": "stats"}]])
            elif cb_data == "back":
                main_menu(chat_id, user_name)
            elif cb_data.startswith("sel_"):
                name = cb_data.replace("sel_", "")
                profiles = get_user_profiles(user_id)
                profile = profiles.get(name)
                if not profile:
                    edit_message(chat_id, msg_id, "❌ Not found", [[{"text": "🔙 Back", "callback_data": "back"}]])
                    return "OK", 200
                cookies = {"session_token": profile["session_token"], "session_data": profile["session_data"]}
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                stats = loop.run_until_complete(fetch_stats(cookies))
                loop.close()
                
                # Ensure no None values
                rank = stats.get("rank") or 0
                elo = stats.get("eloScore") or 0
                chall = stats.get("totalChallenges") or 0
                attempts = stats.get("attemptsLeft") or 0
                
                if attempts == 0:
                    edit_message(chat_id, msg_id, f"❌ No attempts left. Come back tomorrow.", [[{"text": "🔙 Back", "callback_data": "back"}]])
                    return "OK", 200
                
                text = f"✅ <b>Profile: {name}</b>\n\n📊 BEFORE Stats:\n🏆 Rank: {rank}\n⚡ ELO: {elo}\n🎯 Challenges: {chall}\n📋 Attempts: {attempts}\n\nReady to run 3 attempts?"
                keyboard = [[{"text": "▶️ Run Quiz", "callback_data": f"run_{name}"}], [{"text": "🔙 Back", "callback_data": "back"}]]
                edit_message(chat_id, msg_id, text, keyboard)
                set_user_state(user_id, {"selected_profile": name, "cookies": cookies, "stats_before": stats})
            elif cb_data.startswith("run_"):
                state = get_user_state(user_id)
                cookies = state.get("cookies")
                stats_before = state.get("stats_before", {})
                if not cookies:
                    edit_message(chat_id, msg_id, "❌ Session expired", [[{"text": "🔙 Back", "callback_data": "back"}]])
                    return "OK", 200
                
                edit_message(chat_id, msg_id, "🚀 Running 3 attempts... (~20s)", None)
                
                def run():
                    try:
                        cache = load_cache()
                        answers = cache.get("answers", {})
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        result = loop.run_until_complete(run_parallel_attempts(cookies, answers, 3))
                        loop.close()
                        
                        loop2 = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop2)
                        stats_after = loop2.run_until_complete(fetch_stats(cookies))
                        loop2.close()
                        
                        # FIXED: Ensure all values are numbers
                        rank_before = stats_before.get("rank") or 0
                        rank_after = stats_after.get("rank") or 0
                        rank_change = rank_before - rank_after if (rank_before and rank_after) else 0
                        
                        elo_before = stats_before.get("eloScore") or 0
                        elo_after = stats_after.get("eloScore") or 0
                        elo_change = elo_after - elo_before
                        
                        chall_before = stats_before.get("totalChallenges") or 0
                        chall_after = stats_after.get("totalChallenges") or 0
                        chall_change = chall_after - chall_before
                        
                        text = f"✅ <b>Quiz Complete!</b>\n\n📊 BEFORE:\n🏆 Rank: {rank_before}\n⚡ ELO: {elo_before}\n🎯 Challenges: {chall_before}\n\n📊 AFTER:\n🏆 Rank: {rank_after} ({'↑' if rank_change>0 else '↓'}{abs(rank_change)})\n⚡ ELO: {elo_after} ({'+' if elo_change>=0 else ''}{elo_change})\n🎯 Challenges: {chall_after} ({'+' if chall_change>=0 else ''}{chall_change})\n\n📈 Result: {result['total_correct']}/{result['total_questions']} correct"
                        edit_message(chat_id, msg_id, text, [[{"text": "🔙 Menu", "callback_data": "back"}]])
                    except Exception as e:
                        logger.error(f"Quiz error: {e}")
                        edit_message(chat_id, msg_id, f"❌ Error: {e}", [[{"text": "🔙 Back", "callback_data": "back"}]])
                
                threading.Thread(target=run, daemon=True).start()

        return "OK", 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "ERROR", 500

@app.route("/setup", methods=["GET"])
def setup():
    try:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        requests.get(f"{TELEGRAM_API}/deleteWebhook")
        resp = requests.post(f"{TELEGRAM_API}/setWebhook", json={"url": webhook_url})
        if resp.json().get("ok"):
            return f"✅ Webhook: {webhook_url}", 200
        else:
            return f"❌ Failed", 500
    except Exception as e:
        return f"❌ Error: {e}", 500

@app.route("/health", methods=["GET"])
def health():
    return "OK", 200

@app.route("/", methods=["GET"])
def index():
    return "<h1>🤖 IGC Bot</h1><p><a href='/setup'>Setup</a></p>", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
