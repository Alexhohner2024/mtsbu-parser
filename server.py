#!/usr/bin/env python3
"""
Flask webhook server for Telegram bot.
Telegram sends updates directly to /webhook — no Make.com needed.

Features:
- Real-time progress updates via message editing
- Full policy search with end date detection
"""

import os
import sys
import subprocess
import time
from datetime import datetime
from threading import Thread, Lock

import requests
from flask import Flask, jsonify, request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Start Xvfb virtual display so browser runs in non-headless mode
# This helps bypass Cloudflare Turnstile headless detection
try:
    subprocess.Popen(["Xvfb", ":99", "-screen", "0", "1280x720x24", "-nolisten", "tcp"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.environ["DISPLAY"] = ":99"
except Exception:
    pass

from core.finder import find_policy_end, date_to_str, fmt_delta

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ALLOWED_CHAT_ID = os.environ.get("ALLOWED_CHAT_ID", "")


# --- Telegram API helpers ---

def send_telegram(chat_id: str, text: str) -> int:
    """Send a message and return its message_id."""
    resp = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
        timeout=10,
    )
    try:
        return resp.json().get("result", {}).get("message_id")
    except Exception:
        return None


def edit_telegram(chat_id: str, message_id: int, text: str) -> bool:
    """Edit an existing message. Returns True on success."""
    if not message_id:
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText",
            json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": "Markdown",
            },
            timeout=10,
        )
        return resp.json().get("ok", False)
    except Exception:
        return False


class ThrottledEditor:
    """Rate-limited Telegram message editor.
    Telegram allows ~30 edits/sec per chat, but we throttle to ~1/sec
    to avoid spamming the user and hitting limits.
    """

    def __init__(self, chat_id: str, message_id: int, min_interval: float = 0.8):
        self.chat_id = chat_id
        self.message_id = message_id
        self.min_interval = min_interval
        self._last_edit = 0
        self._lock = Lock()
        self._last_text = None

    def update(self, text: str, force: bool = False) -> bool:
        """Edit message with throttling. Returns True if edited."""
        if text == self._last_text:
            return False

        now = time.time()
        with self._lock:
            if not force and (now - self._last_edit) < self.min_interval:
                return False
            self._last_edit = now

        ok = edit_telegram(self.chat_id, self.message_id, text)
        if ok:
            self._last_text = text
        return ok

    def force_update(self, text: str) -> bool:
        """Force edit, ignoring throttle."""
        with self._lock:
            self._last_edit = 0
        return self.update(text, force=True)


# --- Result formatting ---

def format_result(result: dict, query: str) -> str:
    """Format the full search result with end date info."""
    date_str = datetime.now().strftime("%d.%m.%Y")

    if result.get("error"):
        return f"❌ *Помилка*\n🔍 `{query}`\n⚠️ {result['error']}"

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
        lines.append(f"📅 Дата перевірки: {result['statusDate']}")

    # End date info (from binary search)
    if result.get("start_date") and result.get("end_date"):
        lines.append("")
        lines.append(f"📅 Початок:   {result['start_date']}")
        lines.append(f"⏳ Закінчення: {result['end_date']}")
        if result.get("remaining_str"):
            lines.append(f"⏰ Залишилось: {result['remaining_str']}")
        elif result.get("overdue_str"):
            lines.append(f"⚠️ Прострочено: {result['overdue_str']}")

    vehicle = result.get("vehicle", {})
    if vehicle.get("make") or vehicle.get("model"):
        car = " ".join(filter(None, [vehicle.get("make"), vehicle.get("model")]))
        plate = vehicle.get("plate", "")
        lines.append(f"\n🚗 {car}" + (f" | {plate}" if plate else ""))

    company = result.get("company", {})
    if company.get("name"):
        lines.append(f"🏢 {company['name']}")

    if result.get("url") and result["url"].startswith("http"):
        lines.append(f"🔗 [Відкрити поліс]({result['url']})")

    checks = result.get("checks_total")
    if checks:
        lines.append(f"\n📊 Перевірок: {checks}")

    return "\n".join(lines)


def format_progress(icon: str, message: str, query: str) -> str:
    """Format a progress message for Telegram."""
    return f"{icon} {message}\n\n🔍 `{query}` — перевіряю..."


# --- Main check logic ---

def run_check(chat_id: str, query: str, qtype: str):
    """Full policy search with real-time progress via message editing."""
    import traceback

    # Send initial message
    msg_id = send_telegram(chat_id, f"🔍 Перевіряю `{query}`... Зачекайте.")

    def status_cb(icon: str, message: str):
        """Called by finder/checker for every status update."""
        text = format_progress(icon, message, query)
        editor.update(text)

    editor = ThrottledEditor(chat_id, msg_id)

    try:
        policy_number, start_date, end_date, result = find_policy_end(
            query=query,
            search_type=qtype,
            headless=False,
            status_cb=status_cb,
        )

        # Send final result
        if result:
            final_text = format_result(result, query)
        else:
            final_text = f"❌ *Поліс не знайдено*\n🔍 `{query}`"

        editor.force_update(final_text)

    except Exception as e:
        error_text = (
            f"❌ *Помилка*\n"
            f"🔍 `{query}`\n"
            f"```\n{traceback.format_exc()[-400:]}\n```"
        )
        editor.force_update(error_text)


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
        send_telegram(
            chat_id,
            "👋 Привіт! Надішли держномер або VIN-код —\n"
            "перевірю поліс ОСЦПВ і знайду дату закінчення.\n\n"
            "📝 Приклади: `BH4789AK`, `WDB9036611R215291`",
        )
        return jsonify({"ok": True}), 200

    if text.startswith("/"):
        return jsonify({"ok": True}), 200

    if ALLOWED_CHAT_ID and chat_id != ALLOWED_CHAT_ID:
        send_telegram(chat_id, "⛔ Доступ заборонено.")
        return jsonify({"ok": True}), 200

    query = text.upper().strip()
    qtype = detect_type(query)

    Thread(target=run_check, args=(chat_id, query, qtype), daemon=True).start()

    return jsonify({"ok": True}), 200


@app.route("/debug", methods=["GET"])
def debug():
    """Open policy.mtsbu.ua and return detailed element analysis (Patchright)."""
    from patchright.sync_api import sync_playwright
    try:
        pw = sync_playwright().start()
        launch_args = ["--disable-blink-features=AutomationControlled"]
        proxy_url = os.environ.get("PROXY_URL")
        launch_kwargs = {"headless": False, "args": launch_args}
        if proxy_url:
            from urllib.parse import urlparse
            parsed = urlparse(proxy_url)
            proxy_cfg = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
            if parsed.username:
                proxy_cfg["username"] = parsed.username
            if parsed.password:
                proxy_cfg["password"] = parsed.password
            launch_kwargs["proxy"] = proxy_cfg

        browser = pw.chromium.launch(**launch_kwargs)
        page = browser.new_page()
        page.goto("https://policy.mtsbu.ua/", wait_until="load", timeout=60000)
        page.wait_for_timeout(15000)

        result = page.evaluate("""() => {
            const cfWidget = document.querySelector('[name="cf-turnstile-response"]');
            const gWidget = document.querySelector('[name="g-recaptcha-response"]');
            const cfValue = cfWidget ? cfWidget.value : (gWidget ? gWidget.value : null);
            const cfIframe = document.querySelector('iframe[src*="challenges.cloudflare.com"]');
            return {
                turnstile: {
                    cfFieldExists: !!cfWidget,
                    gFieldExists: !!gWidget,
                    fieldValue: cfValue ? cfValue.substring(0, 50) + '...' : '(empty)',
                    iframeExists: !!cfIframe,
                },
                url: window.location.href,
            };
        }""")

        page.close()
        browser.close()
        pw.stop()
        return jsonify(result)
    except Exception as e:
        import traceback
        return jsonify({"error": traceback.format_exc()}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
