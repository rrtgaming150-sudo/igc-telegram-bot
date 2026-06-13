#!/usr/bin/env python3
"""
🎯 INDIA GENIUS CHALLENGE - COMPLETE TELEGRAM BOT
- Accepts JSON files (cookies & answer cache)
- Profile management
- 3 parallel perfect attempts with before/after stats
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
# 📱 TELEGRAM API HELPERS
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
# 🌐 API & STATS
# ═══════════════════════════════════════════════════════════════════════

async def fetch_stats(cookies):
    """Fetch stats using dashboard scraping + API fallback"""
    cookie_dict = {
        "__Secure-better-auth.session_token": cookies.get("session_token", ""),
        "__Secure-better-auth.session_data": cookies.get("session_data", ""),
    }
    stats = {"rank": None, "eloScore": None, "totalChallenges": None, "attemptsLeft": None}

    async with aiohttp.ClientSession() as session:
        # 1. Attempts left
        try:
            async with session.get(f"{BASE_URL}/api/attempt/check", cookies=cookie_dict, timeout=8) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("success"):
                        has_played = data.get("data", False)
                        stats["attemptsLeft"] = 0 if has_played else 3
        except:
            pass

        # 2. Dashboard scraping
        try:
            async with session.get(f"{BASE_URL}/dashboard", cookies=cookie_dict, timeout=10) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    rank_match = re.search(r'Rank[:\s]*([\d,]+)\s*/\s*[\d,]+', html, re.IGNORECASE)
                    if rank_match:
                        stats["rank"] = int(rank_match.group(1).replace(",", ""))
                    gp_match = re.search(r'(?:GP|Genius Points?|ELO)[:\s]*([\d,]+)', html, re.IGNORECASE)
                    if not gp_match:
                        gp_match = re.search(r'>(\d{4})GP<', html)
                    if gp_match:
                        stats["eloScore"] = int(gp_match.group(1).replace(",", ""))
                    chall_match = re.search(r'(?:Challenges?|Challenges Played|Total Challenges)[:\s]*([\d,]+)', html, re.IGNORECASE)
                    if chall_match:
                        stats["totalChallenges"] = int(chall_match.group(1).replace(",", ""))
        except:
            pass

        # 3. Fallback: leaderboard API
        if not stats["rank"] or not stats["totalChallenges"]:
            try:
                async with session.get(f"{BASE_URL}/api/leaderboard", cookies=cookie_dict, timeout=8) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("success"):
                            board = data.get("data", {})
                            stats["rank"] = stats["rank"] or board.get("userRank") or board.get("rank")
                            stats["totalChallenges"] = stats["totalChallenges"] or board.get("userTotalQuizzesAttempted") or board.get("totalPlayed")
            except:
                pass

        # 4. Fallback: user profile API for ELO
        if not stats["eloScore"]:
            try:
                async with session.post(f"{BASE_URL}/api/users/me", cookies=cookie_dict, timeout=8) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("success"):
                            user = data.get("data", {})
                            stats["eloScore"] = user.get("elo") or user.get("eloScore")
            except:
                pass

    return stats

async def generate_attempt(cookies, answers_cache):
    cookie_dict = {
        "__Secure-better-auth.session_token": cookies.get("session_token", ""),
        "__Secure-better-auth.session_data": cookies.get("session_data", ""),
    }
    try:
        async with aiohttp.ClientSession() as session:
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
                    async with session.post(f"{BASE_URL}/api/attempt/validate", json=body, cookies=cookie_dict, timeout=10) as v_resp:
                        if v_resp.status == 200:
                            v_data = await v_resp.json()
                            if v_data.get("success"):
                                attempted = v_data.get("data", {}).get("QuestionsAttempted", [])
                                if attempted and attempted[-1].get("isCorrect"):
                                    correct += 1
                    await asyncio.sleep(0.5)
                return {"correct": correct, "total": total, "id": attempt_id}
    except:
        return None

async def run_parallel_attempts(cookies, answers_cache, n=3):
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
# 🎯 TELEGRAM HANDLERS
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
            marker = " ✅ active" if name == active else ""
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
    text = f"📝 <b>Answer Cache</b>\n\n📅 Date: {cache.get('date')}\n📊 Answers: {count}\n\n<b>Send a JSON file</b> or paste JSON with format:\n<code>{'{\"answers\": {\"question_id\": \"answer\"}}'}</code>"
    keyboard = [[{"text": "🔙 Back", "callback_data": "back"}]]
    if message_id:
        edit_message(chat_id, message_id, text, keyboard)
    else:
        send_message(chat_id, text, keyboard)

# ═══════════════════════════════════════════════════════════════════════
# 🛠 FILE HANDLERS
# ═══════════════════════════════════════════════════════════════════════

def parse_cookie_json(data):
    """Convert cookie JSON (array or object) to dict with session_token and session_data."""
    if isinstance(data, list):
        cookies = {}
        for item in data:
            if item.get("name") == "__Secure-better-auth.session_token":
                cookies["session_token"] = item.get("value")
            elif item.get("name") == "__Secure-better-auth.session_data":
                cookies["session_data"] = item.get("value")
        return cookies
    elif isinstance(data, dict):
        return {
            "session_token": data.get("session_token") or data.get("__Secure-better-auth.session_token"),
            "session_data": data.get("session_data") or data.get("__Secure-better-auth.session_data"),
        }
    return None

# ═══════════════════════════════════════════════════════════════════════
# 🌐 WEBHOOK
# ═══════════════════════════════════════════════════════════════════════

def run_async_in_thread(loop, coro):
    asyncio.set_event_loop(loop)
    loop.run_until_complete(coro)

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

            # Handle file uploads (JSON files)
            if "document" in msg:
                doc = msg["document"]
                if doc.file_name.endswith(".json"):
                    file_info = requests.get(f"{TELEGRAM_API}/getFile?file_id={doc['file_id']}").json()
                    file_path = file_info["result"]["file_path"]
                    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
                    file_content = requests.get(file_url).text
                    try:
                        json_data = json.loads(file_content)
                        # Determine if this is for cookie or cache based on user state
                        if state.get("waiting_profile_data"):
                            # Expecting cookie JSON
                            cookies = parse_cookie_json(json_data)
                            if cookies and cookies.get("session_token") and cookies.get("session_data"):
                                name = state.get("profile_name")
                                save_profile(user_id, name, cookies["session_token"], cookies["session_data"])
                                set_active_profile(user_id, name)
                                set_user_state(user_id, {})
                                send_message(chat_id, f"✅ Profile <code>{name}</code> saved from file!")
                            else:
                                send_message(chat_id, "❌ Invalid cookie file. Missing session tokens.")
                        elif state.get("waiting_cache"):
                            # Expecting answer cache
                            if "answers" in json_data:
                                cur = load_cache()
                                cur["answers"].update(json_data["answers"])
                                save_cache(cur)
                                send_message(chat_id, f"✅ Imported {len(json_data['answers'])} answers from file. Total: {len(cur['answers'])}")
                                set_user_state(user_id, {})
                            else:
                                send_message(chat_id, "❌ Invalid cache file. Need {'answers': {...}}")
                        else:
                            send_message(chat_id, "Please use the menu buttons first, then send the file.")
                    except Exception as e:
                        logger.error(f"File parse error: {e}")
                        send_message(chat_id, f"❌ Error reading JSON file.")
                    return "OK", 200

            # Handle text messages
            if text == "/start":
                main_menu(chat_id, user_name)
            elif state.get("waiting_profile_name"):
                set_user_state(user_id, {"waiting_profile_data": True, "profile_name": text})
                send_message(chat_id, "📄 Send your cookie JSON file (exported from browser) or paste the JSON now.")
            elif state.get("waiting_profile_data") and text:
                # User pasted JSON instead of file
                try:
                    json_data = json.loads(text)
                    cookies = parse_cookie_json(json_data)
                    if cookies and cookies.get("session_token") and cookies.get("session_data"):
                        name = state["profile_name"]
                        save_profile(user_id, name, cookies["session_token"], cookies["session_data"])
                        set_active_profile(user_id, name)
                        set_user_state(user_id, {})
                        send_message(chat_id, f"✅ Profile <code>{name}</code> saved!")
                    else:
                        send_message(chat_id, "❌ Invalid JSON. Missing session tokens.")
                except:
                    send_message(chat_id, "❌ Invalid JSON. Please send a valid JSON file or text.")
            elif state.get("waiting_cache"):
                # User pasted JSON for cache
                try:
                    json_data = json.loads(text)
                    if "answers" in json_data:
                        cur = load_cache()
                        cur["answers"].update(json_data["answers"])
                        save_cache(cur)
                        send_message(chat_id, f"✅ Imported {len(json_data['answers'])} answers. Total: {len(cur['answers'])}")
                        set_user_state(user_id, {})
                    else:
                        send_message(chat_id, "❌ Invalid format. Need {'answers': {...}}")
                except:
                    send_message(chat_id, "❌ Invalid JSON.")
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
                text = "🗑️ Select profile to delete:"
                keyboard = [[{"text": f"❌ Delete {name}", "callback_data": f"del_{name}"}] for name in profiles]
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
                edit_message(chat_id, msg_id, "📥 Send your answer cache JSON file or paste JSON:", [[{"text": "❌ Cancel", "callback_data": "back"}]])
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
                text = f"📊 <b>Stats - {name}</b>\n\n🏆 Rank: {stats.get('rank', 'N/A')}\n⚡ ELO: {stats.get('eloScore', 'N/A')}\n🎯 Challenges: {stats.get('totalChallenges', 'N/A')}\n📋 Attempts left: {stats.get('attemptsLeft', 'N/A')}"
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
                attempts = stats.get("attemptsLeft", 0)
                if attempts == 0:
                    edit_message(chat_id, msg_id, f"❌ No attempts left for {name}. Come back tomorrow.", [[{"text": "🔙 Back", "callback_data": "back"}]])
                    return "OK", 200
                text = f"✅ <b>Profile: {name}</b>\n\n📊 BEFORE Stats:\n🏆 Rank: {stats.get('rank', 'N/A')}\n⚡ ELO: {stats.get('eloScore', 'N/A')}\n🎯 Challenges: {stats.get('totalChallenges', 'N/A')}\n📋 Attempts left: {attempts}\n\nReady to run 3 attempts?"
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
                        rank_before = stats_before.get("rank", 0)
                        rank_after = stats_after.get("rank", rank_before)
                        rank_change = rank_before - rank_after if rank_before and rank_after else 0
                        elo_before = stats_before.get("eloScore", 0)
                        elo_after = stats_after.get("eloScore", elo_before)
                        elo_change = elo_after - elo_before
                        chall_before = stats_before.get("totalChallenges", 0)
                        chall_after = stats_after.get("totalChallenges", chall_before)
                        chall_change = chall_after - chall_before
                        text = f"✅ <b>Quiz Complete!</b>\n\n📊 BEFORE:\nRank: {rank_before}\nELO: {elo_before}\nChallenges: {chall_before}\n\n📊 AFTER:\nRank: {rank_after} ({'↑' if rank_change>0 else '↓'}{abs(rank_change)})\nELO: {elo_after} ({'+' if elo_change>=0 else ''}{elo_change})\nChallenges: {chall_after} ({'+' if chall_change>=0 else ''}{chall_change})\n\n📈 Result: {result['total_correct']}/{result['total_questions']} correct in {result['attempts']} attempts"
                        edit_message(chat_id, msg_id, text, [[{"text": "🔙 Main Menu", "callback_data": "back"}]])
                    except Exception as e:
                        logger.error(f"Quiz run error: {e}")
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
            return f"✅ Webhook set: {webhook_url}", 200
        else:
            return f"❌ Failed: {resp.json()}", 500
    except Exception as e:
        return f"❌ Error: {e}", 500

@app.route("/health", methods=["GET"])
def health():
    return "OK", 200

@app.route("/", methods=["GET"])
def index():
    return "<h1>🤖 IGC Bot</h1><p><a href='/setup'>Setup webhook</a></p>", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
