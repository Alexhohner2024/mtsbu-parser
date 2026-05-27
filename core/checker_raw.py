"""
Raw Playwright checker — no cloakbrowser wrapper.
Uses --headless=new (Chrome's new headless mode, harder to detect)
and manual stealth patches.
"""

import os
import tempfile
from datetime import datetime
from typing import Callable, Optional

from playwright.sync_api import sync_playwright

from core.parser import parse_result_page

StatusCallback = Callable[[str, str], None]


STEALTH_JS = """
// Patch navigator.webdriver
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

// Patch chrome runtime
window.chrome = {runtime: {}, loadTimes: function(){}, csi: function(){}};

// Patch permissions
const origQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (params) =>
    params.name === 'notifications'
        ? Promise.resolve({state: Notification.permission})
        : origQuery(params);

// Patch plugins
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5]
});

// Patch languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['uk-UA', 'uk', 'en-US', 'en']
});
"""


def _save_debug_html(html: str, prefix: str, query: str):
    try:
        ts = datetime.now().strftime("%H%M%S")
        safe = "".join(c if c.isalnum() else "_" for c in query)[:20]
        path = os.path.join(tempfile.gettempdir(), f"mtsbu_raw_{prefix}_{safe}_{ts}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html[:10000])
    except Exception:
        pass


class RawPlaywrightChecker:
    def __init__(self, headless: bool = True, status_cb: Optional[StatusCallback] = None):
        self.headless = headless
        self.status_cb = status_cb
        self._pw = None
        self._browser = None

    def _status(self, icon: str, message: str):
        if self.status_cb:
            self.status_cb(icon, message)

    def _get_browser(self):
        if self._browser is None:
            self._status("🚀", "Запуск Playwright (raw)...")
            self._pw = sync_playwright().start()

            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-first-run",
                "--no-default-browser-check",
            ]

            # Use new headless mode if headless
            if self.headless:
                launch_args.append("--headless=new")

            proxy_url = os.environ.get("PROXY_URL")
            launch_kwargs = {
                "args": launch_args,
                "headless": False,  # We pass --headless=new via args instead
            }

            if proxy_url:
                from urllib.parse import urlparse
                parsed = urlparse(proxy_url)
                proxy_cfg = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
                if parsed.username:
                    proxy_cfg["username"] = parsed.username
                if parsed.password:
                    proxy_cfg["password"] = parsed.password
                launch_kwargs["proxy"] = proxy_cfg
                self._status("🌍", f"Proxy: {parsed.hostname}:{parsed.port}")

            self._browser = self._pw.chromium.launch(**launch_kwargs)
        return self._browser

    def _new_page(self):
        browser = self._get_browser()
        context = browser.new_context(
            viewport={"width": 1366, "height": 768},
            locale="uk-UA",
            timezone_id="Europe/Kyiv",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        )
        context.add_init_script(STEALTH_JS)
        return context.new_page()

    def _submit_and_wait(self, page, query: str):
        self._status("🔍", "Надсилання запиту...")

        submit_btn = page.locator('#submitBtn, button[type="submit"]').first

        # Wait up to 15 sec for Turnstile to enable button
        for _ in range(15):
            try:
                disabled = submit_btn.evaluate("el => el.disabled")
                if not disabled:
                    break
            except Exception:
                pass
            page.wait_for_timeout(1000)

        # Force-enable if still disabled
        try:
            still_disabled = submit_btn.evaluate("el => el.disabled")
            if still_disabled:
                self._status("🔓", "Примусове увімкнення кнопки...")
                page.evaluate("""() => {
                    const btn = document.getElementById('submitBtn');
                    if (btn) btn.disabled = false;
                }""")
                page.wait_for_timeout(500)
        except Exception:
            pass

        original_url = page.url

        # Click submit via JS
        page.evaluate("""() => {
            const btn = document.getElementById('submitBtn');
            if (btn) btn.click();
        }""")
        page.wait_for_timeout(2000)

        self._status("⏳", "Очікування результату...")
        for _ in range(30):
            page.wait_for_timeout(1000)
            current_url = page.url
            html = page.content()

            if current_url != original_url and "Search" in current_url:
                self._status("✅", "Сторінка результату завантажена")
                return html, current_url

            if "поліс" in html.lower() or "policyNumber" in html:
                return html, current_url

        self._status("⚠️", "Тайм-аут, читаємо поточний HTML")
        return page.content(), page.url

    def _check(self, query: str, date: str, tab_selector: str,
               input_selector: str, date_selector: str, label: str) -> dict:
        page = self._new_page()
        try:
            self._status("🌐", "Відкриття policy.mtsbu.ua...")
            page.goto("https://policy.mtsbu.ua/", wait_until="load", timeout=60000)
            page.wait_for_timeout(3000)

            # Check Turnstile status
            self._status("🛡️", "Перевірка Turnstile...")
            for i in range(30):
                solved = page.evaluate("""() => {
                    const f = document.querySelector('[name="cf-turnstile-response"]');
                    return f && f.value && f.value.length > 0;
                }""")
                if solved:
                    self._status("✅", "Turnstile пройдено!")
                    break
                page.wait_for_timeout(1000)
            else:
                self._status("⚠️", "Turnstile не вирішено за 30 сек")

            # Debug: check Turnstile state
            ts_state = page.evaluate("""() => {
                const f = document.querySelector('[name="cf-turnstile-response"]');
                const iframe = document.querySelector('iframe[src*="turnstile"]');
                return {
                    fieldExists: !!f,
                    fieldValue: f ? (f.value || '').substring(0, 30) : null,
                    iframeExists: !!iframe,
                    iframeSrc: iframe ? iframe.src.substring(0, 80) : null
                };
            }""")
            self._status("🔍", f"Turnstile: {ts_state}")

            page.wait_for_timeout(2000)

            # Click tab via JS
            self._status("🔄", f"Вкладка «{label}»...")
            first_selector = tab_selector.split(",")[0].strip()
            page.evaluate(f"""() => {{
                const tab = document.querySelector('{first_selector}');
                if (tab) tab.click();
            }}""")
            page.wait_for_timeout(1000)

            # Fill form via JS
            self._status("✏️", f"Заповнення: {query}...")
            page.evaluate("""(q, d, inpSel, dateSel) => {
                const inp = document.querySelector(inpSel);
                const dateInp = document.querySelector(dateSel);
                if (inp) {
                    inp.value = q;
                    inp.dispatchEvent(new Event('input', {bubbles: true}));
                    inp.dispatchEvent(new Event('change', {bubbles: true}));
                }
                if (dateInp) {
                    dateInp.value = d;
                    dateInp.dispatchEvent(new Event('input', {bubbles: true}));
                    dateInp.dispatchEvent(new Event('change', {bubbles: true}));
                }
            }""", query, date, input_selector, date_selector)

            html, result_url = self._submit_and_wait(page, query)
            result = parse_result_page(html)
            result["url"] = result_url

            if not result.get("found"):
                _save_debug_html(html, label[:3], query)

            return result

        finally:
            try:
                page.context.close()
            except Exception:
                pass

    def check_by_plate(self, plate: str, date: str) -> dict:
        return self._check(
            query=plate, date=date,
            tab_selector='a[href="#carNumber"], a#carNumber-tab',
            input_selector="#RegNoModel_PlateNumber",
            date_selector="#numDate",
            label="За госномером",
        )

    def check_by_vin(self, vin: str, date: str) -> dict:
        return self._check(
            query=vin, date=date,
            tab_selector='a[href="#vin"], a#vin-tab',
            input_selector="#VinModel_VinCode",
            date_selector="#vinDate",
            label="За VIN-кодом",
        )

    def close(self):
        if self._browser:
            self._status("👋", "Закриття браузера...")
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._pw:
            try:
                self._pw.stop()
            except Exception:
                pass
            self._pw = None
