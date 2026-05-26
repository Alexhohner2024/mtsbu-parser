#!/usr/bin/env python3
"""
Flask webhook server for Telegram bot.
Telegram sends updates directly to /webhook — no Make.com needed.
"""

import os
import sys
from datetime import datetime
from threading import Thread

import requests
from flask import Flask, jsonify, request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.checker import MtsbuChecker

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ALLOWED_CHAT_ID = os.environ.get("ALLOWED_CHAT_ID", "")


def send_telegram(chat_id: str, text: str):
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
        timeout=10,
    )


def format_result(result: dict, query: str) -> str:
    date_str = datetime.now().strftime("%d.%m.%Y")

    if not result.get("found"):
        msg = result.get("message", "")
        text = f"❌ *Поліс не знайдено*\n🔍 `{query}` | {date_str}"
        if msg:
            text += f"\nℹ️ {msg}"
        return text

    lines = [f"✅ *Поліс знайдено*", f"🔍 `{query}` | {date_str}"]

    if result.get("policyNumber"):
        lines.append(f"🆔 Номер: `{result['policyNumber']}`")
    if result.get("status"):
        lines.append(f"📌 Статус: {result['status']}")
    if result.get("statusDate"):
        lines.append(f"📅 Дата: {result['statusDate']}")

    vehicle = result.get("vehicle", {})
    if vehicle.get("make") or vehicle.get("model"):
        car = " ".join(filter(None, [vehicle.get("make"), vehicle.get("model")]))
        plate = vehicle.get("plate", "")
        lines.append(f"🚗 {car}" + (f" | {plate}" if plate else ""))

    company = result.get("company", {})
    if company.get("name"):
        lines.append(f"🏢 {company['name']}")

    if result.get("url") and result["url"].startswith("http"):
        lines.append(f"🔗 [Відкрити поліс]({result['url']})")

    return "\n".join(lines)


def run_check(chat_id: str, query: str, qtype: str):
    import traceback
    try:
        send_telegram(chat_id, "🔧 Запускаю браузер...")
        checker = MtsbuChecker(headless=True)
    except Exception as e:
        send_telegram(chat_id, f"⚠️ Помилка запуску браузера:\n`{traceback.format_exc()[-300:]}`")
        return
    try:
        send_telegram(chat_id, "🌐 Браузер запущено, виконую запит...")
        date = datetime.now().strftime("%d.%m.%Y")
        if qtype == "vin":
            result = checker.check_by_vin(query, date)
        else:
            result = checker.check_by_plate(query, date)
        send_telegram(chat_id, format_result(result, query))
    except Exception as e:
        send_telegram(chat_id, f"⚠️ Помилка перевірки:\n`{traceback.format_exc()[-300:]}`")
    finally:
        try:
            checker.close()
        except Exception:
            pass


def detect_type(query: str) -> str:
    if len(query) == 17 and query.isalnum():
        return "vin"
    return "plate"


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": True}), 200

    message = data.get("message") or data.get("edited_message")
    if not message:
        return jsonify({"ok": True}), 200

    chat_id = str(message.get("chat", {}).get("id", ""))
    text = message.get("text", "").strip()

    if not text:
        return jsonify({"ok": True}), 200

    if text == "/start":
        send_telegram(chat_id, "👋 Привіт! Надішли держномер або VIN-код — перевірю поліс ОСАГО.")
        return jsonify({"ok": True}), 200

    if text.startswith("/"):
        return jsonify({"ok": True}), 200

    if ALLOWED_CHAT_ID and chat_id != ALLOWED_CHAT_ID:
        send_telegram(chat_id, "⛔ Доступ заборонено.")
        return jsonify({"ok": True}), 200

    query = text.upper()
    qtype = detect_type(query)

    send_telegram(chat_id, "⏳ Перевіряю, зачекайте до 60 сек...")
    Thread(target=run_check, args=(chat_id, query, qtype), daemon=True).start()

    return jsonify({"ok": True}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
