#!/usr/bin/env python3
"""
Flask webhook server for Telegram bot via Make.com.
Receives POST /check from Make.com, runs MtsbuChecker in background,
then sends the result directly to Telegram Bot API.
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
    checker = MtsbuChecker(headless=True)
    try:
        date = datetime.now().strftime("%d.%m.%Y")
        if qtype == "vin":
            result = checker.check_by_vin(query, date)
        else:
            result = checker.check_by_plate(query, date)
        send_telegram(chat_id, format_result(result, query))
    except Exception as e:
        send_telegram(chat_id, f"⚠️ Помилка під час перевірки:\n`{e}`")
    finally:
        checker.close()


@app.route("/check", methods=["POST"])
def check():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "invalid json"}), 400

    chat_id = str(data.get("chat_id", ""))
    query = str(data.get("query", "")).strip().upper()
    qtype = data.get("type", "plate")

    if not chat_id or not query:
        return jsonify({"error": "chat_id and query required"}), 400

    # Whitelist check — only allowed chat_id may use the service
    if ALLOWED_CHAT_ID and chat_id != ALLOWED_CHAT_ID:
        return jsonify({"error": "forbidden"}), 403

    Thread(target=run_check, args=(chat_id, query, qtype), daemon=True).start()
    return jsonify({"ok": True}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
