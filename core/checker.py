import os
import tempfile
from datetime import datetime
from typing import Callable, Optional

from cloakbrowser import launch

from core.parser import parse_result_page

StatusCallback = Callable[[str, str], None]


def _save_debug_html(html: str, prefix: str, plate: str):
    try:
        ts = datetime.now().strftime("%H%M%S")
        safe = "".join(c if c.isalnum() else "_" for c in plate)[:20]
        path = os.path.join(tempfile.gettempdir(), f"mtsbu_debug_{prefix}_{safe}_{ts}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html[:10000])
    except Exception:
        pass


class MtsbuChecker:
    def __init__(self, headless: bool = False, status_cb: Optional[StatusCallback] = None):
        self.status_cb = status_cb
        self._browser = None

    def _status(self, icon: str, message: str):
        if self.status_cb:
            self.status_cb(icon, message)

    def _get_browser(self):
        if self._browser is None:
            self._status("🚀", "Запуск браузера...")
            proxy_url = os.environ.get("PROXY_URL")
            launch_kwargs = dict(
                headless=False,
                humanize=True,
                args=["--fingerprint=12345"],
            )
            if proxy_url:
                # Parse proxy URL: http://user:pass@host:port
                from urllib.parse import urlparse
                parsed = urlparse(proxy_url)
                proxy_cfg = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
                if parsed.username:
                    proxy_cfg["username"] = parsed.username
                if parsed.password:
                    proxy_cfg["password"] = parsed.password
                launch_kwargs["proxy"] = proxy_cfg
                self._status("🌍", f"Proxy: {parsed.hostname}:{parsed.port}")
            self._browser = launch(**launch_kwargs)
        return self._browser

    def _wait_for_turnstile(self, page):
        """Wait for Cloudflare Turnstile to solve before submitting."""
        self._status("🛡️", "Очікування Cloudflare Turnstile...")
        for _ in range(60):  # up to 60 seconds
            solved = page.evaluate("""() => {
                const f = document.querySelector('[name="cf-turnstile-response"]');
                return f && f.value && f.value.length > 0;
            }""")
            if solved:
                self._status("✅", "Turnstile пройдено")
                return True
            page.wait_for_timeout(1000)
        self._status("⚠️", "Turnstile не вирішено за 60 сек")
        return False

    def _submit_and_wait(self, page, query: str):
        self._status("🔍", "Надсилання запиту...")

        # Try natural Turnstile first (10 sec), then force-enable button
        submit_btn = page.locator('#submitBtn, button[type="submit"], input[type="submit"]').first
        for _ in range(10):
            disabled = submit_btn.evaluate("el => el.disabled")
            if not disabled:
                break
            page.wait_for_timeout(1000)

        # Force-enable if still disabled (bypass client-side Turnstile check)
        still_disabled = submit_btn.evaluate("el => el.disabled")
        if still_disabled:
            self._status("🔓", "Примусове увімкнення кнопки...")
            page.evaluate("""() => {
                const btn = document.getElementById('submitBtn');
                if (btn) btn.disabled = false;
            }""")
            page.wait_for_timeout(500)

        submit_btn.wait_for(state="visible", timeout=10000)

        original_url = page.url

        # Use JS click to bypass actionability checks
        page.evaluate("document.getElementById('submitBtn').click()")
        page.wait_for_timeout(2000)

        self._status("⏳", "Очікування результату...")
        for attempt in range(30):
            page.wait_for_timeout(1000)
            current_url = page.url
            html = page.content()

            if current_url != original_url and "Search" in current_url:
                self._status("✅", "Сторінка результату завантажена")
                return html, current_url

            if "поліс" in html.lower() or "policyNumber" in html:
                return html, current_url

        self._status("⚠️", "Сторінка не змінилась, читаємо поточний HTML")
        html = page.content()
        return html, page.url

    def _check(self, query: str, date: str, tab_selector: str, input_selector: str, date_selector: str, label: str) -> dict:
        browser = self._get_browser()
        page = browser.new_page()
        try:
            self._status("🌐", "Відкриття policy.mtsbu.ua...")
            page.goto("https://policy.mtsbu.ua/", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(3000)

            # Wait for Turnstile to solve
            self._status("🛡️", "Очікування Turnstile...")
            for i in range(30):
                solved = page.evaluate("""() => {
                    const f = document.querySelector('[name="cf-turnstile-response"]');
                    return f && f.value && f.value.length > 0;
                }""")
                if solved:
                    self._status("✅", "Turnstile пройдено")
                    break
                page.wait_for_timeout(1000)

            # Wait for page to fully stabilize
            page.wait_for_timeout(2000)

            self._status("🔄", f"Вибір вкладки «{label}»...")
            # Use JS click to bypass cloakbrowser stability checks
            page.evaluate(f"""() => {{
                const tab = document.querySelector('{tab_selector.split(",")[0].strip()}');
                if (tab) tab.click();
            }}""")
            page.wait_for_timeout(1000)

            self._status("✏️", f"Заповнення форми: {query}...")
            # Fill via JS to bypass cloakbrowser's element stability checks
            page.evaluate(f"""(q, d) => {{
                const inp = document.querySelector('{input_selector}');
                const dateInp = document.querySelector('{date_selector}');
                if (inp) {{
                    inp.value = q;
                    inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                    inp.dispatchEvent(new Event('change', {{bubbles: true}}));
                }}
                if (dateInp) {{
                    dateInp.value = d;
                    dateInp.dispatchEvent(new Event('input', {{bubbles: true}}));
                    dateInp.dispatchEvent(new Event('change', {{bubbles: true}}));
                }}
            }}""", query, date)

            html, result_url = self._submit_and_wait(page, query)

            result = parse_result_page(html)
            result["url"] = result_url

            if not result.get("found"):
                _save_debug_html(html, label[:3], query)
                self._status("⚠️", f"Парсер не знайшов поліс. HTML збережено в {tempfile.gettempdir()}")

            if result.get("found"):
                self._status("✅", "Поліс знайдено!")
            else:
                self._status("❌", "Поліс не знайдено")

            return result

        finally:
            page.close()

    def check_by_plate(self, plate: str, date: str) -> dict:
        return self._check(
            query=plate,
            date=date,
            tab_selector='a[href="#carNumber"], a#carNumber-tab',
            input_selector="#RegNoModel_PlateNumber",
            date_selector="#numDate",
            label="За госномером",
        )

    def check_by_vin(self, vin: str, date: str) -> dict:
        return self._check(
            query=vin,
            date=date,
            tab_selector='a[href="#vin"], a#vin-tab',
            input_selector="#VinModel_VinCode",
            date_selector="#vinDate",
            label="За VIN-кодом",
        )

    def check(self, plate: str, date: str) -> dict:
        return self.check_by_plate(plate, date)

    def close(self):
        if self._browser:
            self._status("👋", "Закриття браузера...")
            self._browser.close()
            self._browser = None
