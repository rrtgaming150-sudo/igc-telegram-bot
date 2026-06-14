#!/usr/bin/env python3
"""
🎯 INDIA GENIUS CHALLENGE - FINAL BOT
- Upload JSON (cookies + answers)
- Save profiles
- Test cookies validity (accepts file or manual paste)
- Run 3 parallel attempts with proper headers
"""

import os
import json
import logging
import asyncio
import aiohttp
import random
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

# ========== BROWSER HEADERS ==========
def get_headers():
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    ]
    return {
        "User-Agent": random.choice(user_agents),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Content-Type": "application/json",
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/quiz",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

# ========== STORAGE ==========
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

# ========== TELEGRAM HELPERS ==========
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

# ========== COOKIE TEST ==========
async def test_cookies_from_dict(cookie_dict):
    cookies = {
        "__Secure-better-auth.session_token": cookie_dict.get("session_token", ""),
        "__Secure-better-auth.session_data": cookie_dict.get("session_data", ""),
    }
    result = {"login_ok": False, "api_ok": False, "questions": 0, "error": None}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{BASE_URL}/dashboard", headers=get_headers(), cookies=cookies, timeout=10) as resp:
                result["login_ok"] = (resp.status == 200)
                if not result["login_ok"]:
                    result["error"] = f"Login failed: {resp.status}"
        except Exception as e:
            result["error"] = str(e)
        if result["login_ok"]:
            await asyncio.sleep(0.5)
            try:
                async with session.post(f"{BASE_URL}/api/attempt/generate", headers=get_headers(), json={}, cookies=cookies, timeout=15) as resp:
                    if resp.status in (200, 201):
                        data = await resp.json()
                        if data.get("success"):
                            result["api_ok"] = True
                            result["questions"] = len(data.get("data", {}).get("questions", []))
                        else:
                            result["error"] = f"API error: {data.get('message')}"
                    else:
                        result["error"] = f"API status: {resp.status}"
            except Exception as e:
                result["error"] = str(e)
    return result

# ========== QUIZ ATTEMPT ==========
async def generate_attempt(cookies, answers_cache):
    cookie_dict = {
        "__Secure-better-auth.session_token": cookies.get("session_token", ""),
        "__Secure-better-auth.session_data": cookies.get("session_data", ""),
    }
    headers = get_headers()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{BASE_URL}/api/attempt/generate", headers=headers, json={}, cookies=cookie_dict, timeout=15) as resp:
                if resp.status not in (200, 201):
                    logger.error(f"Generate failed: {resp.status}")
                    return None
                data = await resp.json()
                if not data.get("success"):
                    logger.error(f"Generate success false: {data}")
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
                    try:
                        async with session.post(f"{BASE_URL}/api/attempt/validate", headers=headers, json=body, cookies=cookie_dict, timeout=10) as v_resp:
                            if v_resp.status == 200:
                                v_data = await v_resp.json()
                                if v_data.get("success"):
                                    attempted = v_data.get("data", {}).get("QuestionsAttempted", [])
                                    if attempted and attempted[-1].get("isCorrect"):
                                        correct += 1
                        await asyncio.sleep(0.3)
                    except Exception as e:
                        logger.error(f"Validate error: {e}")
                return {"correct": correct, "total": total}
    except Exception as e:
        logger.error(f"Generate attempt error: {e}")
        return None

async def run_parallel_attempts(cookies, answers_cache, n=3):
    tasks = [generate_attempt(cookies, answers_cache) for _ in range(n)]
    results = await asyncio.gather(*tasks)
    total_correct = sum(r["correct"] for r in results if r)
    total_questions = sum(r["total"] for r in results if r)
    attempts_completed = len([r for r in results if r])
    return {"attempts": attempts_completed, "correct": total_correct, "total": total_questions}

# ========== HANDLERS ==========
def main_menu(chat_id, user_name):
    text = f"🎯 <b>INDIA GENIUS CHALLENGE BOT</b>\n\n👋 Hi {user_name}!\n\nChoose:"
    keyboard = [
        [{"text": "🎮 Start Quiz", "callback_data": "start_quiz"}],
        [{"text": "👤 Profiles", "callback_data": "profiles"}],
        [{"text": "📝 Answers", "callback_data": "cache"}],
        [{"text": "🔧 Test Cookies", "callback_data": "test_cookies"}],
    ]
    send_message(chat_id, text, keyboard)

def show_profiles(chat_id, user_id, message_id=None):
    profiles = get_user_profiles(user_id)
    text = "👤 <b>Profiles</b>\n\n"
    if profiles:
        for name in profiles.keys():
            text += f"  • {name}\n"
    else:
        text += "No profiles.\n"
    keyboard = [[{"text": "➕ Add", "callback_data": "add_profile"}]]
    if profiles:
        keyboard.append([{"text": "🗑️ Delete", "callback_data": "delete_profile"}])
    keyboard.append([{"text": "🔙 Back", "callback_data": "back"}])
    if message_id:
        edit_message(chat_id, message_id, text, keyboard)
    else:
        send_message(chat_id, text, keyboard)

def show_cache(chat_id, message_id=None):
    cache = load_cache()
    count = len(cache.get("answers", {}))
    text = f"📝 <b>Answer Cache</b>\n\nAnswers: {count}\n\nSend JSON file"
    keyboard = [[{"text": "🔙 Back", "callback_data": "back"}]]
    if message_id:
        edit_message(chat_id, message_id, text, keyboard)
    else:
        send_message(chat_id, text, keyboard)

# ========== FILE PARSING ==========
def is_cookie_file(json_data):
    if isinstance(json_data, list):
        for item in json_data:
            if isinstance(item, dict) and item.get("name") in ("__Secure-better-auth.session_token", "__Secure-better-auth.session_data"):
                return True
    elif isinstance(json_data, dict):
        if "__Secure-better-auth.session_token" in json_data or "session_token" in json_data:
            return True
    return False

def parse_cookie_json(data):
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

# ========== WEBHOOK ==========
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

            # Handle file upload
            if "document" in msg:
                doc = msg["document"]
                if doc["file_name"].endswith(".json"):
                    file_info = requests.get(f"{TELEGRAM_API}/getFile?file_id={doc['file_id']}").json()
                    if not file_info.get("ok"):
                        send_message(chat_id, "❌ Failed to get file.")
                        return "OK", 200
                    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info['result']['file_path']}"
                    try:
                        file_content = requests.get(file_url).text
                        json_data = json.loads(file_content)
                    except Exception as e:
                        send_message(chat_id, f"❌ Error reading file: {e}")
                        return "OK", 200

                    # If user is in test cookies state, treat as cookie test
                    if state.get("waiting_test_file"):
                        clear_user_state(user_id)
                        cookies = parse_cookie_json(json_data)
                        if cookies:
                            send_message(chat_id, "⏳ Testing cookies...")
                            def test():
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                result = loop.run_until_complete(test_cookies_from_dict(cookies))
                                loop.close()
                                if result["login_ok"] and result["api_ok"]:
                                    msg = f"✅ <b>Cookies valid!</b>\n\nLogin: OK\nAPI: OK\nQuestions: {result['questions']}"
                                elif result["login_ok"]:
                                    msg = f"⚠️ <b>Partial issue</b>\n\nLogin: OK\nAPI: Failed\nError: {result['error']}"
                                else:
                                    msg = f"❌ <b>Cookies invalid</b>\n\nError: {result['error']}"
                                send_message(chat_id, msg, [[{"text": "Menu", "callback_data": "back"}]])
                            threading.Thread(target=test, daemon=True).start()
                        else:
                            send_message(chat_id, "❌ Invalid cookie file.")
                        return "OK", 200

                    # Otherwise, normal profile or answer cache
                    if is_cookie_file(json_data):
                        if state.get("waiting_profile_data"):
                            name = state.get("profile_name")
                        else:
                            set_user_state(user_id, {"waiting_profile_name": True, "pending_cookie_data": json_data})
                            send_message(chat_id, "📝 Enter profile name:")
                            return "OK", 200
                        cookies = parse_cookie_json(json_data)
                        if cookies:
                            save_profile(user_id, name, cookies["session_token"], cookies["session_data"])
                            clear_user_state(user_id)
                            send_message(chat_id, f"✅ Profile <b>{name}</b> saved!")
                        else:
                            send_message(chat_id, "❌ Invalid cookie file.")
                    else:
                        # Answer cache
                        new_answers = {}
                        if "answers" in json_data and isinstance(json_data["answers"], dict):
                            new_answers = json_data["answers"]
                        elif isinstance(json_data, list):
                            for item in json_data:
                                qid = item.get("question_id")
                                ans = item.get("correct_answer")
                                if qid and ans:
                                    new_answers[qid] = ans
                        if new_answers:
                            cur = load_cache()
                            cur["answers"].update(new_answers)
                            save_cache(cur)
                            send_message(chat_id, f"✅ {len(new_answers)} answers added. Total: {len(cur['answers'])}")
                            clear_user_state(user_id)
                        else:
                            send_message(chat_id, "❌ Invalid answer cache format.")
                    return "OK", 200

            # Text commands
            if text == "/start":
                main_menu(chat_id, user_name)
            elif state.get("waiting_profile_name"):
                if "pending_cookie_data" in state:
                    cookies = parse_cookie_json(state["pending_cookie_data"])
                    if cookies:
                        save_profile(user_id, text, cookies["session_token"], cookies["session_data"])
                        clear_user_state(user_id)
                        send_message(chat_id, f"✅ Profile <b>{text}</b> saved!")
                    else:
                        send_message(chat_id, "❌ Invalid cookie data.")
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
                        clear_user_state(user_id)
                        send_message(chat_id, f"✅ Profile <b>{name}</b> saved!")
                    else:
                        send_message(chat_id, "❌ Invalid cookie JSON.")
                except:
                    send_message(chat_id, "❌ Invalid JSON. Send a file or paste correctly.")
            elif state.get("waiting_test_token"):
                set_user_state(user_id, {"waiting_test_data": True, "test_token": text})
                send_message(chat_id, "🔐 Paste session data:")
            elif state.get("waiting_test_data"):
                token = state["test_token"]
                data_val = text
                clear_user_state(user_id)
                send_message(chat_id, "⏳ Testing cookies...")
                def test():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    result = loop.run_until_complete(test_cookies_from_dict({"session_token": token, "session_data": data_val}))
                    loop.close()
                    if result["login_ok"] and result["api_ok"]:
                        msg = f"✅ <b>Cookies valid!</b>\n\nLogin: OK\nAPI: OK\nQuestions: {result['questions']}"
                    elif result["login_ok"]:
                        msg = f"⚠️ <b>Partial issue</b>\n\nLogin: OK\nAPI: Failed\nError: {result['error']}"
                    else:
                        msg = f"❌ <b>Cookies invalid</b>\n\nError: {result['error']}"
                    send_message(chat_id, msg, [[{"text": "Menu", "callback_data": "back"}]])
                threading.Thread(target=test, daemon=True).start()
            else:
                send_message(chat_id, "Send /start")

        elif "callback_query" in data:
            cb = data["callback_query"]
            chat_id = cb["message"]["chat"]["id"]
            msg_id = cb["message"]["message_id"]
            user_id = cb["from"]["id"]
            user_name = cb["from"].get("first_name", "User")
            cb_data = cb.get("data", "")
            answer_callback(cb["id"])

            if cb_data == "start_quiz":
                profiles = get_user_profiles(user_id)
                if not profiles:
                    edit_message(chat_id, msg_id, "❌ No profiles. Add one first.",
                                 [[{"text": "➕ Add", "callback_data": "add_profile"}], [{"text": "🔙 Back", "callback_data": "back"}]])
                    return "OK", 200
                text = "📋 Select profile:"
                keyboard = [[{"text": name, "callback_data": f"sel_{name}"}] for name in profiles]
                keyboard.append([{"text": "🔙 Back", "callback_data": "back"}])
                edit_message(chat_id, msg_id, text, keyboard)

            elif cb_data == "profiles":
                show_profiles(chat_id, user_id, msg_id)
            elif cb_data == "add_profile":
                set_user_state(user_id, {"waiting_profile_name": True})
                edit_message(chat_id, msg_id, "📝 Enter profile name:", [[{"text": "❌ Cancel", "callback_data": "back"}]])
            elif cb_data == "delete_profile":
                profiles = get_user_profiles(user_id)
                if not profiles:
                    edit_message(chat_id, msg_id, "No profiles to delete.", [[{"text": "🔙 Back", "callback_data": "profiles"}]])
                    return "OK", 200
                text = "🗑️ Select profile to delete:"
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
            elif cb_data == "test_cookies":
                keyboard = [
                    [{"text": "📄 Send Cookie File", "callback_data": "test_file"}],
                    [{"text": "✏️ Paste Manually", "callback_data": "test_paste"}],
                    [{"text": "🔙 Back", "callback_data": "back"}],
                ]
                edit_message(chat_id, msg_id, "🔧 <b>Test Cookies</b>\n\nChoose method:", keyboard)
            elif cb_data == "test_file":
                set_user_state(user_id, {"waiting_test_file": True})
                edit_message(chat_id, msg_id, "📄 Send your cookie JSON file.", [[{"text": "❌ Cancel", "callback_data": "back"}]])
            elif cb_data == "test_paste":
                set_user_state(user_id, {"waiting_test_token": True})
                edit_message(chat_id, msg_id, "🔐 Paste session token:", [[{"text": "❌ Cancel", "callback_data": "back"}]])
            elif cb_data == "back":
                main_menu(chat_id, user_name)
            elif cb_data.startswith("sel_"):
                name = cb_data.replace("sel_", "")
                profiles = get_user_profiles(user_id)
                profile = profiles.get(name)
                if not profile:
                    edit_message(chat_id, msg_id, "Profile not found", [[{"text": "🔙 Back", "callback_data": "back"}]])
                    return "OK", 200
                text = f"✅ <b>{name}</b>\n\nReady to run 3 quizzes?"
                keyboard = [[{"text": "🚀 Run 3 Quizzes", "callback_data": f"run_{name}"}], [{"text": "🔙 Back", "callback_data": "back"}]]
                edit_message(chat_id, msg_id, text, keyboard)
                set_user_state(user_id, {"selected_profile": name, "cookies": {"session_token": profile["session_token"], "session_data": profile["session_data"]}})
            elif cb_data.startswith("run_"):
                state = get_user_state(user_id)
                cookies = state.get("cookies")
                if not cookies:
                    edit_message(chat_id, msg_id, "❌ Session expired", [[{"text": "🔙 Back", "callback_data": "back"}]])
                    return "OK", 200
                edit_message(chat_id, msg_id, "⏳ Running 3 quizzes (~20s)...", None)
                def run():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    cache = load_cache()
                    answers = cache.get("answers", {})
                    result = loop.run_until_complete(run_parallel_attempts(cookies, answers, 3))
                    loop.close()
                    text = f"✅ <b>Quiz Complete!</b>\n\n🎮 Attempts: {result['attempts']}/3\n✨ Correct: {result['correct']}/{result['total']}"
                    edit_message(chat_id, msg_id, text, [[{"text": "🏠 Menu", "callback_data": "back"}]])
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
        return "❌ Failed", 500
    except Exception as e:
        return f"❌ Error: {e}", 500

@app.route("/health", methods=["GET"])
def health():
    return "OK", 200

@app.route("/", methods=["GET"])
def index():
    return "<h1>🤖 IGC Bot - Final</h1><p><a href='/setup'>Setup Webhook</a></p>", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
