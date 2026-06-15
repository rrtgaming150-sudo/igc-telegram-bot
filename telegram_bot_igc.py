#!/usr/bin/env python3
"""
🎯 INDIA GENIUS CHALLENGE - TELEGRAM BOT
Based on the working parallel triple attempt script
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

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/json",
    "origin": BASE_URL,
    "referer": f"{BASE_URL}/quiz",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

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

def load_cache():
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except:
            return {}
    return {}

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

def answer_callback(callback_id):
    try:
        requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json={"callback_query_id": callback_id}, timeout=10)
    except:
        pass

# ═══════════════════════════════════════════════════════════════════════
# 🌐 QUIZ LOGIC - Based on the working script
# ═══════════════════════════════════════════════════════════════════════

async def generate_attempt(session, attempt_num):
    """Generate a single attempt"""
    try:
        async with session.post(f"{BASE_URL}/api/attempt/generate", json={}, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status not in (200, 201):
                return None
            
            data = await resp.json()
            if not data.get("success"):
                return None
            
            attempt = data["data"]["attempt"]
            questions = data["data"]["quiz"]["Questions"]
            
            return {
                "num": attempt_num,
                "attemptId": attempt["_id"],
                "questionSet": attempt["QuestionSet"],
                "questions": questions,
                "q_by_id": {q["_id"]: q for q in questions},
                "correct": 0,
            }
    except Exception as e:
        logger.error(f"Generate error: {e}")
    
    return None

async def answer_question(session, attempt, question_idx, question_id, ANSWERS):
    """Answer a single question"""
    question = attempt["q_by_id"].get(question_id, {})
    answer_text = ANSWERS.get(question_id)
    
    if not answer_text:
        return False
    
    body = {
        "_id": attempt["attemptId"],
        "questionId": question_id,
        "question": question.get("question", ""),
        "selectedAnswer": answer_text,
        "timeSpent": 3,
    }
    
    try:
        async with session.post(f"{BASE_URL}/api/attempt/validate", json=body, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("success"):
                    attempted = data.get("data", {}).get("QuestionsAttempted", [])
                    last = attempted[-1] if attempted else {}
                    if last.get("isCorrect", False):
                        attempt["correct"] += 1
                        return True
            await asyncio.sleep(0.8)
            return False
    except Exception as e:
        logger.error(f"Answer error: {e}")
        await asyncio.sleep(0.8)
    
    return False

async def run_triple_parallel(cookie_str, ANSWERS):
    """Run 3 parallel attempts - based on working script"""
    cookies = {}
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            cookies[k.strip()] = v.strip()
    
    connector = aiohttp.TCPConnector(limit=20)
    session = aiohttp.ClientSession(connector=connector, headers=HEADERS, cookies=cookies)
    
    try:
        # Generate 3 attempts
        attempt_tasks = [generate_attempt(session, i+1) for i in range(3)]
        attempts = await asyncio.gather(*attempt_tasks)
        attempts = [a for a in attempts if a is not None]
        
        if not attempts:
            return {"attempts": 0, "correct": 0, "total": 0, "error": "Failed to generate attempts"}
        
        # Answer questions across attempts
        max_questions = max(len(att["questionSet"]) for att in attempts)
        
        for q_idx in range(max_questions):
            answer_tasks = []
            for att in attempts:
                if q_idx < len(att["questionSet"]):
                    qid = att["questionSet"][q_idx]
                    answer_tasks.append(answer_question(session, att, q_idx, qid, ANSWERS))
                else:
                    answer_tasks.append(asyncio.sleep(0))
            
            await asyncio.gather(*answer_tasks)
            await asyncio.sleep(0.8)
        
        # Calculate totals
        total_correct = sum(att["correct"] for att in attempts)
        total_questions = sum(len(att["questionSet"]) for att in attempts)
        
        return {
            "attempts": len(attempts),
            "correct": total_correct,
            "total": total_questions,
            "per_attempt": [{"num": a["num"], "correct": a["correct"], "total": len(a["questionSet"])} for a in attempts],
        }
    
    except Exception as e:
        logger.error(f"Run error: {e}")
        return {"attempts": 0, "correct": 0, "total": 0, "error": str(e)}
    
    finally:
        await session.close()

# ═══════════════════════════════════════════════════════════════════════
# 🎯 HANDLERS
# ═══════════════════════════════════════════════════════════════════════

def main_menu(chat_id, user_name):
    text = f"🎯 <b>IGC PARALLEL BOT</b>\n\n👋 Hi {user_name}!\n\nChoose:"
    keyboard = [
        [{"text": "🎮 Start Quiz", "callback_data": "start_quiz"}],
        [{"text": "👤 Profiles", "callback_data": "profiles"}],
        [{"text": "📝 Answers", "callback_data": "cache"}],
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
    count = len(cache)
    text = f"📝 <b>Answer Cache</b>\n\nAnswers: {count}\n\nSend JSON file"
    keyboard = [[{"text": "🔙 Back", "callback_data": "back"}]]
    if message_id:
        edit_message(chat_id, message_id, text, keyboard)
    else:
        send_message(chat_id, text, keyboard)

# ═══════════════════════════════════════════════════════════════════════
# 🛠 FILE HANDLERS
# ═══════════════════════════════════════════════════════════════════════

def is_cookie_file(json_data):
    if isinstance(json_data, list):
        for item in json_data:
            if isinstance(item, dict):
                if item.get("name") in ("__Secure-better-auth.session_token", "__Secure-better-auth.session_data"):
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

def parse_answers_json(json_data):
    """Parse answers from both formats"""
    answers = {}
    
    if isinstance(json_data, dict) and "answers" in json_data:
        # Format: {"answers": {"id": "answer"}}
        if isinstance(json_data["answers"], dict):
            answers.update(json_data["answers"])
    elif isinstance(json_data, list):
        # Format: [{"question_id": "...", "correct_answer": "..."}]
        for item in json_data:
            qid = item.get("question_id") or item.get("_id") or item.get("id")
            ans = item.get("correct_answer") or item.get("answer")
            if qid and ans:
                answers[qid] = ans
    
    return answers

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

            if "document" in msg:
                doc = msg["document"]
                if doc["file_name"].endswith(".json"):
                    file_info = requests.get(f"{TELEGRAM_API}/getFile?file_id={doc['file_id']}").json()
                    if not file_info.get("ok"):
                        send_message(chat_id, "Failed to get file.")
                        return "OK", 200
                    
                    file_path = file_info["result"]["file_path"]
                    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
                    
                    try:
                        file_content = requests.get(file_url).text
                        json_data = json.loads(file_content)
                    except Exception as e:
                        send_message(chat_id, f"Error: {e}")
                        return "OK", 200

                    if is_cookie_file(json_data):
                        if state.get("waiting_profile_data"):
                            name = state.get("profile_name")
                        else:
                            set_user_state(user_id, {"waiting_profile_name": True, "pending_cookie_data": json_data})
                            send_message(chat_id, "Enter profile name:")
                            return "OK", 200
                        
                        cookies = parse_cookie_json(json_data)
                        if cookies:
                            save_profile(user_id, name, cookies["session_token"], cookies["session_data"])
                            clear_user_state(user_id)
                            send_message(chat_id, f"✅ Profile saved: {name}")
                        else:
                            send_message(chat_id, "Invalid cookies.")
                    else:
                        answers = parse_answers_json(json_data)
                        if answers:
                            cache = load_cache()
                            cache.update(answers)
                            save_cache(cache)
                            send_message(chat_id, f"✅ {len(answers)} answers added. Total: {len(cache)}")
                            clear_user_state(user_id)
                        else:
                            send_message(chat_id, "Invalid answer format.")
                    
                    return "OK", 200

            if text == "/start":
                main_menu(chat_id, user_name)
            elif state.get("waiting_profile_name"):
                if "pending_cookie_data" in state:
                    cookies = parse_cookie_json(state["pending_cookie_data"])
                    if cookies:
                        save_profile(user_id, text, cookies["session_token"], cookies["session_data"])
                        clear_user_state(user_id)
                        send_message(chat_id, f"✅ Profile saved: {text}")
                    else:
                        send_message(chat_id, "Invalid.")
                else:
                    set_user_state(user_id, {"waiting_profile_data": True, "profile_name": text})
                    send_message(chat_id, "Send cookie JSON file or paste.")
            elif state.get("waiting_profile_data") and text:
                try:
                    json_data = json.loads(text)
                    cookies = parse_cookie_json(json_data)
                    if cookies:
                        save_profile(user_id, state["profile_name"], cookies["session_token"], cookies["session_data"])
                        clear_user_state(user_id)
                        send_message(chat_id, f"✅ Profile saved: {state['profile_name']}")
                    else:
                        send_message(chat_id, "Invalid format.")
                except:
                    send_message(chat_id, "Invalid JSON.")
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
                    edit_message(chat_id, msg_id, "No profiles.", [[{"text": "Add", "callback_data": "add_profile"}], [{"text": "Back", "callback_data": "back"}]])
                    return "OK", 200
                text = "Select profile:"
                keyboard = [[{"text": name, "callback_data": f"sel_{name}"}] for name in profiles]
                keyboard.append([{"text": "Back", "callback_data": "back"}])
                edit_message(chat_id, msg_id, text, keyboard)

            elif cb_data == "profiles":
                show_profiles(chat_id, user_id, msg_id)
            elif cb_data == "add_profile":
                set_user_state(user_id, {"waiting_profile_name": True})
                edit_message(chat_id, msg_id, "Profile name:", [[{"text": "Cancel", "callback_data": "back"}]])
            elif cb_data == "delete_profile":
                profiles = get_user_profiles(user_id)
                text = "Delete:"
                keyboard = [[{"text": f"Delete {name}", "callback_data": f"del_{name}"}] for name in profiles]
                keyboard.append([{"text": "Back", "callback_data": "back"}])
                edit_message(chat_id, msg_id, text, keyboard)
            elif cb_data.startswith("del_"):
                name = cb_data.replace("del_", "")
                if delete_profile(user_id, name):
                    edit_message(chat_id, msg_id, f"Deleted {name}", [[{"text": "Back", "callback_data": "profiles"}]])
                else:
                    edit_message(chat_id, msg_id, "Not found", [[{"text": "Back", "callback_data": "profiles"}]])
            elif cb_data == "cache":
                show_cache(chat_id, msg_id)
            elif cb_data == "back":
                main_menu(chat_id, user_name)
            elif cb_data.startswith("sel_"):
                name = cb_data.replace("sel_", "")
                profiles = get_user_profiles(user_id)
                profile = profiles.get(name)
                if not profile:
                    edit_message(chat_id, msg_id, "Not found", [[{"text": "Back", "callback_data": "back"}]])
                    return "OK", 200
                
                cookie_str = f"__Secure-better-auth.session_token={profile['session_token']}; __Secure-better-auth.session_data={profile['session_data']}"
                text = f"Profile: <b>{name}</b>\n\nReady to run?"
                keyboard = [[{"text": "Run 3 Quizzes", "callback_data": f"run_{name}"}], [{"text": "Back", "callback_data": "back"}]]
                edit_message(chat_id, msg_id, text, keyboard)
                set_user_state(user_id, {"selected_profile": name, "cookie_str": cookie_str})
            
            elif cb_data.startswith("run_"):
                state = get_user_state(user_id)
                cookie_str = state.get("cookie_str")
                
                if not cookie_str:
                    edit_message(chat_id, msg_id, "Expired", [[{"text": "Back", "callback_data": "back"}]])
                    return "OK", 200
                
                edit_message(chat_id, msg_id, "⏳ Running 3 quizzes...", None)
                
                def run():
                    try:
                        cache = load_cache()
                        
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        result = loop.run_until_complete(run_triple_parallel(cookie_str, cache))
                        loop.close()
                        
                        if result.get("error"):
                            text = f"❌ Error: {result['error']}"
                        else:
                            text = f"""✅ <b>Quiz Complete!</b>

🎮 Attempts: {result['attempts']}/3"""
                            
                            for att in result.get("per_attempt", []):
                                text += f"\n  Attempt {att['num']}: {att['correct']}/{att['total']}"
                            
                            text += f"\n\n✨ Total: {result['correct']}/{result['total']} correct"
                        
                        edit_message(chat_id, msg_id, text, [[{"text": "Menu", "callback_data": "back"}]])
                    except Exception as e:
                        edit_message(chat_id, msg_id, f"❌ Error: {str(e)[:100]}", [[{"text": "Back", "callback_data": "back"}]])
                
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
    return "<h1>🎮 IGC Parallel Bot</h1><p><a href='/setup'>Setup Webhook</a></p>", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
