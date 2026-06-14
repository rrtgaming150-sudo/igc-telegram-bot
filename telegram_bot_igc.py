#!/usr/bin/env python3
"""
🎯 INDIA GENIUS CHALLENGE - DEBUG BOT
Logs all stats fetching and answer matching
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

# Enhanced logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
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
DEBUG_FILE = STORAGE_DIR / "debug.log"

app = Flask(__name__)

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
            return {"date": datetime.now().strftime("%Y-%m-%d"), "answers": {}}
    return {"date": datetime.now().strftime("%Y-%m-%d"), "answers": {}}

def save_cache(data):
    CACHE_FILE.write_text(json.dumps(data, indent=2))

def log_debug(msg):
    """Log to file and console"""
    logger.info(msg)
    try:
        with open(DEBUG_FILE, "a") as f:
            f.write(f"{datetime.now()} - {msg}\n")
    except:
        pass

def get_user_state(user_id):
    if USER_STATE_FILE.exists():
        try:
            return json.loads(USER_STATE_FILE.read_text()).get(str(user_id), {})
        except:
            return {}
    return {}

def set_user_state(user_id, state):
    states = {}
    if USER_STATE_FILE.exists():
        try:
            states = json.loads(USER_STATE_FILE.read_text())
        except:
            pass
    states[str(user_id)] = state
    USER_STATE_FILE.write_text(json.dumps(states, indent=2))

def clear_user_state(user_id):
    if USER_STATE_FILE.exists():
        try:
            states = json.loads(USER_STATE_FILE.read_text())
            if str(user_id) in states:
                del states[str(user_id)]
                USER_STATE_FILE.write_text(json.dumps(states, indent=2))
        except:
            pass

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

# ═══════════════════════════════════════════════════════════════════════
# 🌐 API & STATS - WITH DEBUG
# ═══════════════════════════════════════════════════════════════════════

async def fetch_stats(cookies):
    """Fetch stats with debug logging"""
    log_debug("=== FETCHING STATS ===")
    
    cookie_dict = {
        "__Secure-better-auth.session_token": cookies.get("session_token", ""),
        "__Secure-better-auth.session_data": cookies.get("session_data", ""),
    }
    
    stats = {
        "rank": 0,
        "eloScore": 0,
        "totalChallenges": 0,
        "attemptsLeft": 3
    }
    
    async with aiohttp.ClientSession() as session:
        # Fetch dashboard HTML
        try:
            log_debug("Fetching dashboard...")
            async with session.get(f"{BASE_URL}/dashboard", cookies=cookie_dict, timeout=10) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    log_debug(f"Dashboard HTML length: {len(html)}")
                    
                    # Debug: save first 2000 chars
                    log_debug(f"Dashboard HTML (first 2000 chars): {html[:2000]}")
                    
                    # Parse Rank
                    rank_match = re.search(r'Rank[:\s]*([\d,]+)\s*/\s*[\d,]+', html, re.IGNORECASE)
                    if rank_match:
                        stats["rank"] = int(rank_match.group(1).replace(",", ""))
                        log_debug(f"Found Rank: {stats['rank']}")
                    else:
                        log_debug("Rank pattern NOT matched")
                    
                    # Parse ELO
                    gp_match = re.search(r'(?:GP|ELO|Score)[:\s]*([\d,]+)', html, re.IGNORECASE)
                    if gp_match:
                        stats["eloScore"] = int(gp_match.group(1).replace(",", ""))
                        log_debug(f"Found ELO: {stats['eloScore']}")
                    else:
                        log_debug("ELO pattern NOT matched")
                    
                    # Parse Challenges
                    chall_match = re.search(r'(?:Challenge|Played)[:\s]*([\d,]+)', html, re.IGNORECASE)
                    if chall_match:
                        stats["totalChallenges"] = int(chall_match.group(1).replace(",", ""))
                        log_debug(f"Found Challenges: {stats['totalChallenges']}")
                    else:
                        log_debug("Challenges pattern NOT matched")
                else:
                    log_debug(f"Dashboard request failed with status: {resp.status}")
        except Exception as e:
            log_debug(f"Dashboard fetch error: {e}")
    
    log_debug(f"Final stats: {stats}")
    return stats

async def generate_attempt(cookies, answers_cache):
    """Generate and answer with debug logging"""
    log_debug("=== GENERATING ATTEMPT ===")
    log_debug(f"Answers in cache: {len(answers_cache)}")
    
    cookie_dict = {
        "__Secure-better-auth.session_token": cookies.get("session_token", ""),
        "__Secure-better-auth.session_data": cookies.get("session_data", ""),
    }
    try:
        async with aiohttp.ClientSession() as session:
            log_debug("Posting generate attempt...")
            async with session.post(f"{BASE_URL}/api/attempt/generate", json={}, cookies=cookie_dict, timeout=15) as resp:
                log_debug(f"Generate response status: {resp.status}")
                if resp.status not in (200, 201):
                    log_debug(f"Generate failed with status {resp.status}")
                    return None
                
                data = await resp.json()
                if not data.get("success"):
                    log_debug(f"Generate not successful: {data}")
                    return None
                
                attempt = data.get("data", {})
                attempt_id = attempt.get("_id")
                questions = attempt.get("questions", [])
                
                log_debug(f"Attempt ID: {attempt_id}")
                log_debug(f"Questions: {len(questions)}")
                
                # Debug: Log first 3 question IDs
                for i, q in enumerate(questions[:3]):
                    qid = q.get("_id")
                    log_debug(f"  Question {i}: ID = {qid}")
                
                correct = 0
                total = len(questions)
                
                for q in questions:
                    qid = q.get("_id")
                    ans = answers_cache.get(qid)
                    
                    if not ans:
                        log_debug(f"  Q {qid}: NOT FOUND in cache")
                        continue
                    
                    log_debug(f"  Q {qid}: FOUND - Answer: {ans}")
                    
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
                                        log_debug(f"    ✅ CORRECT")
                                    else:
                                        log_debug(f"    ❌ WRONG")
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        log_debug(f"    Error validating: {e}")
                
                log_debug(f"Attempt result: {correct}/{total}")
                return {"correct": correct, "total": total, "id": attempt_id}
    except Exception as e:
        log_debug(f"Generate attempt error: {e}")
    
    return None

async def run_parallel_attempts(cookies, answers_cache, n=3):
    """Run attempts with debug"""
    log_debug(f"=== RUNNING {n} PARALLEL ATTEMPTS ===")
    tasks = [generate_attempt(cookies, answers_cache) for _ in range(n)]
    results = await asyncio.gather(*tasks)
    
    total_correct = sum(r["correct"] for r in results if r)
    total_questions = sum(r["total"] for r in results if r)
    
    log_debug(f"Total results: {total_correct}/{total_questions}")
    return {
        "attempts": len([r for r in results if r]),
        "total_correct": total_correct,
        "total_questions": total_questions,
        "per_attempt": results
    }

# ═══════════════════════════════════════════════════════════════════════
# 🌐 WEBHOOK
# ═══════════════════════════════════════════════════════════════════════

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        
        if "callback_query" in data:
            cb = data["callback_query"]
            chat_id = cb["message"]["chat"]["id"]
            msg_id = cb["message"]["message_id"]
            user_id = cb["from"]["id"]
            cb_data = cb.get("data", "")
            
            if cb_data.startswith("run_"):
                state = get_user_state(user_id)
                cookies = state.get("cookies")
                
                if not cookies:
                    edit_message(chat_id, msg_id, "Session expired", [[{"text": "Back", "callback_data": "back"}]])
                    return "OK", 200
                
                edit_message(chat_id, msg_id, "Running 3 attempts... (~20s)", None)
                
                def run():
                    try:
                        log_debug(f"\n\n{'='*50}")
                        log_debug(f"QUIZ START - User {user_id}")
                        log_debug(f"{'='*50}\n")
                        
                        cache = load_cache()
                        answers = cache.get("answers", {})
                        
                        log_debug(f"Cache size: {len(answers)}")
                        log_debug(f"First 5 answers: {list(answers.items())[:5]}")
                        
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        result = loop.run_until_complete(run_parallel_attempts(cookies, answers, 3))
                        loop.close()
                        
                        loop2 = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop2)
                        stats_after = loop2.run_until_complete(fetch_stats(cookies))
                        loop2.close()
                        
                        text = f"Quiz Complete!\n\nResult: {result['total_correct']}/{result['total_questions']}\n\n📋 Check debug logs for details!"
                        edit_message(chat_id, msg_id, text, [[{"text": "Menu", "callback_data": "back"}]])
                        
                        log_debug(f"\n{'='*50}")
                        log_debug(f"QUIZ END")
                        log_debug(f"{'='*50}\n")
                    except Exception as e:
                        logger.error(f"Quiz error: {e}")
                        edit_message(chat_id, msg_id, f"Error: {e}", [[{"text": "Back", "callback_data": "back"}]])
                
                threading.Thread(target=run, daemon=True).start()
        
        return "OK", 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "ERROR", 500

@app.route("/logs", methods=["GET"])
def logs():
    """View debug logs"""
    try:
        if DEBUG_FILE.exists():
            content = DEBUG_FILE.read_text()
            return f"<pre>{content}</pre>", 200
        else:
            return "No logs yet", 200
    except:
        return "Error reading logs", 500

@app.route("/clear-logs", methods=["GET"])
def clear_logs():
    """Clear debug logs"""
    try:
        if DEBUG_FILE.exists():
            DEBUG_FILE.write_text("")
        return "Logs cleared", 200
    except:
        return "Error clearing logs", 500

@app.route("/setup", methods=["GET"])
def setup():
    try:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        requests.get(f"{TELEGRAM_API}/deleteWebhook")
        resp = requests.post(f"{TELEGRAM_API}/setWebhook", json={"url": webhook_url})
        if resp.json().get("ok"):
            return f"Webhook set: {webhook_url}", 200
        else:
            return f"Failed", 500
    except Exception as e:
        return f"Error: {e}", 500

@app.route("/health", methods=["GET"])
def health():
    return "OK", 200

@app.route("/", methods=["GET"])
def index():
    return "<h1>IGC Bot - DEBUG</h1><p><a href='/logs'>View Logs</a> | <a href='/clear-logs'>Clear Logs</a> | <a href='/setup'>Setup</a></p>", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    log_debug("Bot started")
    app.run(host="0.0.0.0", port=port, debug=False)
