"""
Patchright-based checker — patched Playwright that bypasses bot detection.
Replaces the old Raw Playwright + stealth JS approach.
"""

import os
import tempfile
from datetime import datetime
from typing import Callable, Optional

from core.parser import parse_result_page

StatusCallback = Callable[[str, str], None]


def _save_debug_html(html: str, prefix: str, query: str):
    try:
        ts = datetime.now().strftime("%H%M%S")
        safe = "".join(c if c.isalnum() else "_" for c in query)[:20]
        path = os.path.join(tempfile.gettempdir(), f"mtsbu_raw_{prefix}_{safe}_{ts}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
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
            self._status("🚀", "Запуск Patchright...")
            from patchright.sync_api import sync_playwright

            self._pw = sync_playwright().start()

            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ]

            launch_kwargs = {
                "headless": self.headless,
                "args": launch_args,
            }

            proxy_url = os.environ.get("PROXY_URL")
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
        )
        return context.new_page()

    def _wait_for_turnstile(self, page):
        """Wait for Cloudflare Turnstile, with click fallback."""
        self._status("🛡️", "Очікування Turnstile...")

        # Phase 1: auto-solve
        for i in range(30):
            solved = page.evaluate("""() => {
                const f = document.querySelector('[name="g-recaptcha-response"]');
                if (f && f.value && f.value.length > 0) return true;
                const f2 = document.querySelector('[name="cf-turnstile-response"]');
                if (f2 && f2.value && f2.value.length > 0) return true;
                return false;
            }""")
            if solved:
                self._status("✅", "Turnstile пройдено!")
                return True
            page.wait_for_timeout(1000)

        # Phase 2: try clicking
        self._status("🖱️", "Спроба кліку по Turnstile...")
        try:
            iframe_el = page.query_selector('iframe[src*="challenges.cloudflare.com"]')
            if not iframe_el:
                iframe_el = page.query_selector('iframe[src*="turnstile"]')
            if iframe_el:
                frame = iframe_el.content_frame()
                if frame:
                    checkbox = frame.query_selector('input[type="checkbox"]')
                    if checkbox:
                        checkbox.click()
                    else:
                        body = frame.query_selector("body")
                        if body:
                            body.click()

                # Wait for solve after click
                for _ in range(15):
                    solved = page.evaluate("""() => {
                        const f = document.querySelector('[name="g-recaptcha-response"]');
                        if (f && f.value && f.value.length > 0) return true;
                        const f2 = document.querySelector('[name="cf-turnstile-response"]');
                        if (f2 && f2.value && f2.value.length > 0) return true;
                        return false;
                    }""")
                    if solved:
                        self._status("✅", "Turnstile пройдено (клік)")
                        return True
                    page.wait_for_timeout(1000)
        except Exception as e:
            self._status("⚠️", f"Помилка кліку Turnstile: {e}")

        self._status("⚠️", "Turnstile не вирішено за 45 сек")
        return False

    def _submit_and_wait(self, page, query: str):
        self._status("🔍", "Надсилання запиту...")

        # Check Turnstile (both field names)
        turnstile_ok = page.evaluate("""() => {
            const f = document.querySelector('[name="g-recaptcha-response"]');
            if (f && f.value && f.value.length > 0) return true;
            const f2 = document.querySelector('[name="cf-turnstile-response"]');
            if (f2 && f2.value && f2.value.length > 0) return true;
            return false;
        }""")

        if not turnstile_ok:
            self._status("⚠️", "Turnstile не вирішено — форму не подано")
            return page.content(), page.url

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

            if current_url != original_url:
                is_result = any(p in current_url for p in ["/Search/ByRegNo", "/Search/ByVin", "/Search/ByPolicy"])
                is_form = "/Search/Main" in current_url
                if is_result:
                    self._status("✅", "Сторінка результату завантажена")
                    return html, current_url
                if is_form:
                    self._status("⚠️", "Сервер повернув сторінку форми")
                    return html, current_url

            if "#notFound" in html or "not-found" in html.lower():
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

            turnstile_solved = self._wait_for_turnstile(page)

            if not turnstile_solved:
                self._status("❌", "Turnstile не вирішено")
                return {
                    "found": False,
                    "error": "Cloudflare Turnstile не вирішено.",
                }

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
