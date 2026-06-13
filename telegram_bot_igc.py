#!/usr/bin/env python3
"""
🎯 India Genius Challenge - Complete Telegram Bot
- Profile management with cookies
- Answer cache collection (probe attempts)
- 3 parallel quiz attempts using IGC parallel script
- All features via buttons
- Webhook deployment ready
"""

import os
import json
import logging
import asyncio
import aiohttp
import random
import time
import re
import unicodedata
from pathlib import Path
from datetime import datetime, date
from flask import Flask, request
import requests
import threading

# ═══════════════════════════════════════════════════════════════════════
# 🔧 CONFIG
# ═══════════════════════════════════════════════════════════════════════

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8966464433:AAHWg3nbvK-d1yFUxJ3LdrqIgTcnvYNhTsg")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://igc-telegram-bot.onrender.com")
BASE_URL = "https://www.indiageniuschallenge.com"
API_URL = f"{BASE_URL}/api"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

STORAGE_DIR = Path("data")
STORAGE_DIR.mkdir(exist_ok=True)

PROFILES_FILE = STORAGE_DIR / "profiles.json"
CACHE_FILE = STORAGE_DIR / "answers_cache.json"
PROBE_STATS_FILE = STORAGE_DIR / "probe_stats.json"
USER_STATE_FILE = STORAGE_DIR / "user_states.json"
IDS_FILE = STORAGE_DIR / "saved_ids.json"

QUIZ_KEY = f"daily_{date.today().isoformat()}"

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

def load_probe_stats():
    if PROBE_STATS_FILE.exists():
        try:
            return json.loads(PROBE_STATS_FILE.read_text())
        except:
            return {"questions": {}}
    return {"questions": {}}

def save_probe_stats(data):
    PROBE_STATS_FILE.write_text(json.dumps(data, indent=2))

def load_user_state():
    if USER_STATE_FILE.exists():
        try:
            return json.loads(USER_STATE_FILE.read_text())
        except:
            return {}
    return {}

def save_user_state(data):
    USER_STATE_FILE.write_text(json.dumps(data, indent=2))

def load_all_ids():
    if IDS_FILE.exists():
        try:
            return json.loads(IDS_FILE.read_text())
        except:
            return {}
    return {}

def save_all_ids(data):
    IDS_FILE.write_text(json.dumps(data, indent=2))

def get_user_state(user_id):
    states = load_user_state()
    return states.get(str(user_id), {})

def set_user_state(user_id, state):
    states = load_user_state()
    states[str(user_id)] = state
    save_user_state(states)

def get_user_profiles(user_id):
    profiles = load_profiles()
    return profiles.get(str(user_id), {})

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

def get_ids_for_user(user_id):
    return load_all_ids().get(str(user_id), [])

def save_ids_for_user(user_id, ids):
    data = load_all_ids()
    data[str(user_id)] = ids[:3]
    save_all_ids(data)

def merged_quiz_cache(cache):
    merged = {}
    for key in cache:
        if key.startswith("daily_") and isinstance(cache[key], dict):
            merged.update(cache[key])
    return merged

def normalize_answer(s):
    s = str(s).strip()
    s = " ".join(s.split())
    return s.lower()

def answers_match(a, b):
    return normalize_answer(a) == normalize_answer(b)

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
# 🌐 API HELPERS (for answer collection and firing)
# ═══════════════════════════════════════════════════════════════════════

def get_browser_headers():
    profiles = [
        {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"},
        {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36"},
    ]
    profile = random.choice(profiles)
    return {
        "User-Agent": profile["User-Agent"],
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/quiz",
    }

async def generate_attempt(session, cookies=None):
    if cookies is None:
        cookies = {}
    try:
        async with session.post(f"{API_URL}/attempt/generate", headers=get_browser_headers(), cookies=cookies, json={}) as resp:
            anon_cookie = None
            for morsel in resp.cookies.values():
                if morsel.key == "anon_attempt_id":
                    anon_cookie = morsel.value
            data = await resp.json(content_type=None)
            if data and data.get("success"):
                quiz = data["data"]["quiz"]
                attempt = data["data"]["attempt"]
                return attempt["_id"], quiz["Questions"], anon_cookie
    except Exception as e:
        logger.error(f"Generate error: {e}")
    return None, None, None

async def validate_answer(session, cookies, attempt_id, question, selected_answer, time_spent, total_time_used=None):
    payload = {
        "_id": attempt_id,
        "questionId": question["_id"],
        "question": question.get("question", ""),
        "selectedAnswer": selected_answer,
        "timeSpent": time_spent,
    }
    if total_time_used is not None:
        payload["totalTimeUsed"] = total_time_used
    try:
        async with session.post(f"{API_URL}/attempt/validate", headers=get_browser_headers(), cookies=cookies, json=payload) as resp:
            if resp.status == 200:
                data = await resp.json(content_type=None)
                if data and data.get("success"):
                    for entry in data.get("data", {}).get("QuestionsAttempted", []):
                        if entry.get("questionId") == question["_id"]:
                            return entry.get("isCorrect", False)
    except Exception as e:
        logger.error(f"Validate error: {e}")
    return False

async def fetch_attempt_details(session, attempt_id):
    try:
        async with session.get(f"{API_URL}/attempt/{attempt_id}", headers=get_browser_headers(), cookies={"anon_attempt_id": attempt_id}) as resp:
            data = await resp.json(content_type=None)
            if data and data.get("success"):
                return data.get("data", {}).get("questions", [])
    except Exception as e:
        logger.error(f"Fetch attempt error: {e}")
    return []

async def update_cache_from_attempt(session, attempt_id, quiz_cache, probe_stats):
    correct_data = await fetch_attempt_details(session, attempt_id)
    newly_learned = 0
    for q in correct_data:
        qid = q.get("_id")
        correct_answer = q.get("answer")
        if not qid or not correct_answer:
            continue
        if qid not in probe_stats.get("questions", {}):
            probe_stats.setdefault("questions", {})[qid] = {"appearances": 0, "cached": False}
        probe_stats["questions"][qid]["correct_answer"] = correct_answer
        if qid not in quiz_cache or not answers_match(quiz_cache[qid], correct_answer):
            quiz_cache[qid] = correct_answer
            newly_learned += 1
            probe_stats["questions"][qid]["cached"] = True
        else:
            probe_stats["questions"][qid]["cached"] = True
    if newly_learned > 0:
        cache = load_cache()
        cache[QUIZ_KEY] = quiz_cache
        cache["question_meta"] = cache.get("question_meta", {})
        save_cache(cache)
        save_probe_stats(probe_stats)
    return newly_learned

# ═══════════════════════════════════════════════════════════════════════
# 🔍 PROBE ATTEMPT (COLLECT ANSWERS)
# ═══════════════════════════════════════════════════════════════════════

async def run_probe_attempt(session, quiz_cache, question_meta, tried_options, run_num, probe_stats):
    attempt_id, questions, _ = await generate_attempt(session)
    if not attempt_id:
        return 0
    for q in questions:
        qid = q["_id"]
        if qid not in probe_stats.get("questions", {}):
            probe_stats.setdefault("questions", {})[qid] = {"appearances": 0, "cached": False}
        probe_stats["questions"][qid]["appearances"] = probe_stats["questions"][qid].get("appearances", 0) + 1
        if qid not in question_meta:
            question_meta[qid] = {"question": q.get("question", ""), "options": q.get("options", [])}
    selections = {}
    for q in questions:
        qid = q["_id"]
        if qid in quiz_cache:
            selections[qid] = quiz_cache[qid]
        else:
            if qid not in tried_options:
                tried_options[qid] = {"tried_contents": []}
            tried_norm = {normalize_answer(c) for c in tried_options[qid]["tried_contents"]}
            untried = [opt for opt in q["options"] if normalize_answer(opt) not in tried_norm]
            if not untried:
                tried_options[qid] = {"tried_contents": []}
                untried = q["options"]
            opt = untried[0]
            tried_options[qid]["tried_contents"].append(opt)
            selections[qid] = opt
    for i, q in enumerate(questions):
        t = round(random.uniform(1.6, 2.2), 2)
        await validate_answer(session, {}, attempt_id, q, selections[q["_id"]], t)
        await asyncio.sleep(random.uniform(0.2, 0.4))
    return await update_cache_from_attempt(session, attempt_id, quiz_cache, probe_stats)

async def collect_answers(session, num_runs=30):
    cache = load_cache()
    quiz_cache = merged_quiz_cache(cache)
    question_meta = dict(cache.get("question_meta", {}))
    tried_options = {}
    probe_stats = load_probe_stats()
    total_learned = 0
    for i in range(1, num_runs + 1):
        learned = await run_probe_attempt(session, quiz_cache, question_meta, tried_options, i, probe_stats)
        total_learned += learned
        logger.info(f"Probe {i}: learned {learned}, cache={len(quiz_cache)}")
        await asyncio.sleep(random.uniform(3, 6))
    cache[QUIZ_KEY] = quiz_cache
    cache["question_meta"] = question_meta
    cache["tried_options"] = tried_options
    save_cache(cache)
    save_probe_stats(probe_stats)
    return quiz_cache

# ═══════════════════════════════════════════════════════════════════════
# 🚀 PARALLEL QUIZ FIRING (IGC PARALLEL SCRIPT)
# ═══════════════════════════════════════════════════════════════════════

async def create_perfect_attempt(session, quiz_cache, cookies, fixed_time_per_question=1.3):
    cookie_dict = {
        "__Secure-better-auth.session_token": cookies.get("session_token", ""),
        "__Secure-better-auth.session_data": cookies.get("session_data", ""),
    }
    attempt_id, questions, anon_cookie = await generate_attempt(session, cookies=cookie_dict)
    if not attempt_id:
        return None, None, 0, 0
    correct = 0
    total = len(questions)
    for i, q in enumerate(questions):
        qid = q["_id"]
        answer = quiz_cache.get(qid)
        if not answer and q.get("options"):
            answer = q["options"][0]
        if not answer:
            continue
        val_cookies = {**cookie_dict, "anon_attempt_id": anon_cookie} if anon_cookie else cookie_dict
        is_correct = await validate_answer(
            session, val_cookies, attempt_id, q, answer, fixed_time_per_question,
            total_time_used=round(fixed_time_per_question * (i+1), 2) if i == total-1 else None
        )
        if is_correct:
            correct += 1
        await asyncio.sleep(0.15)
    return anon_cookie, round(fixed_time_per_question * total, 1), correct, total

async def run_parallel_attempts(session, quiz_cache, cookies, n=3):
    results = []
    for i in range(n):
        aid, elapsed, correct, total = await create_perfect_attempt(session, quiz_cache, cookies)
        results.append((aid, elapsed, correct, total))
        await asyncio.sleep(0.5)
    return results

async def run_single_quiz(session, quiz_cache, cookies):
    return await create_perfect_attempt(session, quiz_cache, cookies)

async def link_anonymous_ids(cookies, anon_ids):
    """Link anonymous IDs to profile"""
    results = []
    cookie_dict = {
        "__Secure-better-auth.session_token": cookies.get("session_token", ""),
        "__Secure-better-auth.session_data": cookies.get("session_data", ""),
    }
    async with aiohttp.ClientSession() as session:
        for aid in anon_ids:
            try:
                c = cookie_dict.copy()
                c["anon_attempt_id"] = aid
                async with session.get(f"{API_URL}/attempt/linkAnon", headers=get_browser_headers(), cookies=c) as resp:
                    results.append((aid, resp.status))
            except Exception as e:
                results.append((aid, str(e)))
    return results

# ═══════════════════════════════════════════════════════════════════════
# 🎯 HANDLERS
# ═══════════════════════════════════════════════════════════════════════

def main_menu(chat_id, user_name):
    text = f"""
🎯 <b>INDIA GENIUS CHALLENGE BOT</b>

👋 Welcome, {user_name}!

Choose an option:
"""
    keyboard = [
        [{"text": "🎮 Start Quiz", "callback_data": "start_quiz"}],
        [{"text": "👤 Profiles", "callback_data": "profiles"}],
        [{"text": "📚 Answer Cache", "callback_data": "cache"}],
        [{"text": "📊 Stats", "callback_data": "stats"}],
        [{"text": "🔗 Link IDs", "callback_data": "link_ids"}],
    ]
    send_message(chat_id, text, keyboard)

def show_profiles(chat_id, user_id, message_id=None):
    profiles = get_user_profiles(user_id)
    text = "👤 <b>Your Profiles</b>\n\n"
    if profiles:
        for name in profiles.keys():
            text += f"  ✅ {name}\n"
    else:
        text += "No profiles yet\n"
    
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
    quiz_cache = merged_quiz_cache(cache)
    cache_count = len(quiz_cache)
    
    text = f"""
📝 <b>Answer Cache</b>

📅 Date: {cache.get('date', 'Unknown')}
📊 Cached Answers: {cache_count}

What to do?
"""
    keyboard = [
        [{"text": "🔍 Collect Answers (30 probes)", "callback_data": "collect_30"}],
        [{"text": "⚡ Quick Collect (10 probes)", "callback_data": "collect_10"}],
        [{"text": "🔙 Back", "callback_data": "back"}],
    ]
    if message_id:
        edit_message(chat_id, message_id, text, keyboard)
    else:
        send_message(chat_id, text, keyboard)

def show_link_ids_menu(chat_id, user_id, message_id=None):
    ids = get_ids_for_user(user_id)
    text = "🔗 <b>Link Anonymous IDs</b>\n\n"
    if ids:
        text += "Saved IDs:\n"
        for i, aid in enumerate(ids, 1):
            text += f"  {i}. <code>{aid}</code>\n"
    else:
        text += "No saved IDs.\n\n"
    text += "\nUse /setids id1 id2 id3 to save IDs"
    
    keyboard = [
        [{"text": "🚀 Link All Saved IDs", "callback_data": "link_all"}],
        [{"text": "➕ Add IDs", "callback_data": "add_ids"}],
        [{"text": "🔙 Back", "callback_data": "back"}],
    ]
    if message_id:
        edit_message(chat_id, message_id, text, keyboard)
    else:
        send_message(chat_id, text, keyboard)

# ═══════════════════════════════════════════════════════════════════════
# 🌐 WEBHOOK
# ═══════════════════════════════════════════════════════════════════════

def run_async_in_thread(loop, coro):
    """Run async coroutine in a separate thread"""
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
            
            if text == "/start":
                main_menu(chat_id, user_name)
            
            elif state.get("waiting_profile_name"):
                set_user_state(user_id, {"waiting_token": True, "profile_name": text})
                send_message(chat_id, "🔐 <b>Enter Session Token</b>\n\nFrom Browser → F12 → Cookies → __Secure-better-auth.session_token")
            
            elif state.get("waiting_token"):
                set_user_state(user_id, {"waiting_data": True, "profile_name": state.get("profile_name"), "session_token": text})
                send_message(chat_id, "🔐 <b>Enter Session Data</b>\n\nFrom Browser → F12 → Cookies → __Secure-better-auth.session_data")
            
            elif state.get("waiting_data"):
                profile_name = state.get("profile_name")
                token = state.get("session_token")
                data_val = text
                save_profile(user_id, profile_name, token, data_val)
                set_active_profile(user_id, profile_name)
                set_user_state(user_id, {})
                send_message(chat_id, f"✅ <b>Profile Saved!</b>\n\nProfile: <code>{profile_name}</code>")
            
            elif state.get("waiting_ids"):
                ids = text.strip().split()
                save_ids_for_user(user_id, ids[:3])
                set_user_state(user_id, {})
                send_message(chat_id, f"✅ Saved {len(ids[:3])} ID(s)")
            
            else:
                send_message(chat_id, "👋 Send /start to begin!")
        
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
                    edit_message(chat_id, msg_id, "❌ <b>No Profiles!</b>\n\nCreate one first.",
                        [[{"text": "➕ Add Profile", "callback_data": "add_profile"}], [{"text": "🔙 Back", "callback_data": "back"}]])
                    return "OK", 200
                
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
                edit_message(chat_id, msg_id, "📝 <b>Enter Profile Name</b>\n\nExample: MainAccount",
                    [[{"text": "❌ Cancel", "callback_data": "back"}]])
            
            elif cb_data == "delete_profile":
                profiles = get_user_profiles(user_id)
                text = "🗑️ <b>Select profile to delete:</b>"
                keyboard = []
                for name in profiles.keys():
                    keyboard.append([{"text": f"❌ Delete {name}", "callback_data": f"del_{name}"}])
                keyboard.append([{"text": "🔙 Back", "callback_data": "back"}])
                edit_message(chat_id, msg_id, text, keyboard)
            
            elif cb_data.startswith("del_"):
                profile_name = cb_data.replace("del_", "")
                if delete_profile(user_id, profile_name):
                    text = f"✅ Deleted profile: {profile_name}"
                else:
                    text = f"❌ Failed to delete: {profile_name}"
                edit_message(chat_id, msg_id, text, [[{"text": "🔙 Back", "callback_data": "profiles"}]])
            
            elif cb_data == "cache":
                show_cache(chat_id, msg_id)
            
            elif cb_data == "collect_30":
                edit_message(chat_id, msg_id, "🔍 Running 30 probe attempts...\n⏳ This may take 5-10 minutes...")
                loop = asyncio.new_event_loop()
                threading.Thread(target=lambda: run_async_in_thread(loop, run_collect_and_report(chat_id, msg_id, 30)), daemon=True).start()
            
            elif cb_data == "collect_10":
                edit_message(chat_id, msg_id, "🔍 Running 10 probe attempts...\n⏳ This may take 2-3 minutes...")
                loop = asyncio.new_event_loop()
                threading.Thread(target=lambda: run_async_in_thread(loop, run_collect_and_report(chat_id, msg_id, 10)), daemon=True).start()
            
            elif cb_data == "link_ids":
                show_link_ids_menu(chat_id, user_id, msg_id)
            
            elif cb_data == "add_ids":
                set_user_state(user_id, {"waiting_ids": True})
                edit_message(chat_id, msg_id, "📝 <b>Enter Anonymous IDs</b>\n\nSend 3 IDs separated by spaces:\n<code>id1 id2 id3</code>",
                    [[{"text": "❌ Cancel", "callback_data": "back"}]])
            
            elif cb_data == "link_all":
                ids = get_ids_for_user(user_id)
                if not ids:
                    edit_message(chat_id, msg_id, "❌ No saved IDs!", [[{"text": "🔙 Back", "callback_data": "link_ids"}]])
                    return "OK", 200
                
                nickname, profile = get_active_profile(user_id)
                if not profile:
                    edit_message(chat_id, msg_id, "❌ No active profile!", [[{"text": "🔙 Back", "callback_data": "profiles"}]])
                    return "OK", 200
                
                edit_message(chat_id, msg_id, "🔗 Linking IDs...\n⏳ Please wait...")
                loop = asyncio.new_event_loop()
                threading.Thread(target=lambda: run_async_in_thread(loop, run_link_ids_and_report(chat_id, msg_id, profile, ids)), daemon=True).start()
            
            elif cb_data == "stats":
                cache = load_cache()
                quiz_cache = merged_quiz_cache(cache)
                probe_stats = load_probe_stats()
                total_known = len(probe_stats.get("questions", {}))
                text = f"📊 <b>Stats</b>\n\n📚 Cached Answers: {len(quiz_cache)}\n🎯 Total Questions Known: {total_known}\n📅 Date: {date.today().isoformat()}"
                keyboard = [[{"text": "🔙 Back", "callback_data": "back"}]]
                edit_message(chat_id, msg_id, text, keyboard)
            
            elif cb_data == "back":
                main_menu(chat_id, user_name)
            
            elif cb_data.startswith("sel_"):
                profile_name = cb_data.replace("sel_", "")
                profiles = get_user_profiles(user_id)
                profile = profiles.get(profile_name)
                
                if profile:
                    set_active_profile(user_id, profile_name)
                    text = f"✅ <b>Profile Selected!</b>\n\nProfile: <code>{profile_name}</code>\n\n🎮 Ready to run quiz?"
                    keyboard = [
                        [{"text": "▶️ Run 3 Parallel Attempts", "callback_data": f"run_parallel_{profile_name}"}],
                        [{"text": "🎯 Run Single Quiz", "callback_data": f"run_single_{profile_name}"}],
                        [{"text": "🔙 Back", "callback_data": "back"}],
                    ]
                    edit_message(chat_id, msg_id, text, keyboard)
            
            elif cb_data.startswith("run_parallel_"):
                profile_name = cb_data.replace("run_parallel_", "")
                profiles = get_user_profiles(user_id)
                profile = profiles.get(profile_name)
                cache = load_cache()
                quiz_cache = merged_quiz_cache(cache)
                
                if not profile or not quiz_cache:
                    edit_message(chat_id, msg_id, "❌ Missing profile or answers!", [[{"text": "🔙 Back", "callback_data": "back"}]])
                    return "OK", 200
                
                edit_message(chat_id, msg_id, "🚀 <b>Running 3 Parallel Attempts</b>\n\n⏳ This may take 30-45 seconds...")
                loop = asyncio.new_event_loop()
                threading.Thread(target=lambda: run_async_in_thread(loop, run_parallel_and_report(chat_id, msg_id, profile, quiz_cache, 3)), daemon=True).start()
            
            elif cb_data.startswith("run_single_"):
                profile_name = cb_data.replace("run_single_", "")
                profiles = get_user_profiles(user_id)
                profile = profiles.get(profile_name)
                cache = load_cache()
                quiz_cache = merged_quiz_cache(cache)
                
                if not profile or not quiz_cache:
                    edit_message(chat_id, msg_id, "❌ Missing profile or answers!", [[{"text": "🔙 Back", "callback_data": "back"}]])
                    return "OK", 200
                
                edit_message(chat_id, msg_id, "🎯 <b>Running Single Quiz</b>\n\n⏳ Please wait...")
                loop = asyncio.new_event_loop()
                threading.Thread(target=lambda: run_async_in_thread(loop, run_single_and_report(chat_id, msg_id, profile, quiz_cache)), daemon=True).start()
        
        return "OK", 200
    
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "ERROR", 500

# ═══════════════════════════════════════════════════════════════════════
# 🔄 BACKGROUND TASKS
# ═══════════════════════════════════════════════════════════════════════

async def run_collect_and_report(chat_id, msg_id, num_runs):
    connector = aiohttp.TCPConnector(limit=50)
    async with aiohttp.ClientSession(connector=connector) as session:
        quiz_cache = await collect_answers(session, num_runs)
    edit_message(chat_id, msg_id, f"✅ <b>Collection Complete!</b>\n\n📚 Cache Size: {len(quiz_cache)}", 
                 [[{"text": "🔙 Back", "callback_data": "back"}]])

async def run_parallel_and_report(chat_id, msg_id, profile, quiz_cache, n):
    connector = aiohttp.TCPConnector(limit=10)
    async with aiohttp.ClientSession(connector=connector) as session:
        results = await run_parallel_attempts(session, quiz_cache, profile, n)
    
    lines = []
    for i, (aid, elapsed, correct, total) in enumerate(results):
        if aid:
            lines.append(f"✅ <b>Attempt {i+1}</b>: {correct}/{total} correct ({elapsed}s)\n🆔 <code>{aid}</code>")
        else:
            lines.append(f"❌ <b>Attempt {i+1}</b>: Failed")
    
    text = "🚀 <b>Quiz Results</b>\n\n" + "\n\n".join(lines)
    edit_message(chat_id, msg_id, text, [[{"text": "🔙 Main Menu", "callback_data": "back"}]])

async def run_single_and_report(chat_id, msg_id, profile, quiz_cache):
    connector = aiohttp.TCPConnector(limit=10)
    async with aiohttp.ClientSession(connector=connector) as session:
        aid, elapsed, correct, total = await run_single_quiz(session, quiz_cache, profile)
    
    if aid:
        text = f"🎯 <b>Quiz Completed!</b>\n\n📊 Score: {correct}/{total} correct\n⏱️ Time: {elapsed}s\n🆔 <code>{aid}</code>"
    else:
        text = "❌ <b>Quiz Failed!</b>\n\nCould not create attempt."
    
    edit_message(chat_id, msg_id, text, [[{"text": "🔙 Main Menu", "callback_data": "back"}]])

async def run_link_ids_and_report(chat_id, msg_id, profile, ids):
    results = await link_anonymous_ids(profile, ids)
    lines = []
    for aid, status in results:
        icon = "✅" if status == 201 else "❌"
        lines.append(f"{icon} <code>{aid[:16]}...</code> → HTTP {status}")
    
    text = "🔗 <b>Link Results</b>\n\n" + "\n".join(lines)
    edit_message(chat_id, msg_id, text, [[{"text": "🔙 Back", "callback_data": "link_ids"}]])

# ═══════════════════════════════════════════════════════════════════════
# 🌐 FLASK ROUTES
# ═══════════════════════════════════════════════════════════════════════

@app.route("/setup", methods=["GET"])
def setup():
    try:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        requests.get(f"{TELEGRAM_API}/deleteWebhook")
        response = requests.post(f"{TELEGRAM_API}/setWebhook", json={"url": webhook_url})
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
    <p>Bot: IGC Parallel Quiz Bot</p>
    <p><a href="/setup">🔧 Setup Webhook</a></p>
    """, 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"🤖 Bot running on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)
