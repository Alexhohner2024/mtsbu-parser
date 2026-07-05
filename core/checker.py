import os
import tempfile
from datetime import datetime
from typing import Callable, Optional

from core.parser import parse_result_page

StatusCallback = Callable[[str, str], None]

TURNSTILE_IFRAME_URL = "https://challenges.cloudflare.com/cdn-cgi/challenge-platform/"


def _save_debug_html(html: str, prefix: str, plate: str):
    try:
        ts = datetime.now().strftime("%H%M%S")
        safe = "".join(c if c.isalnum() else "_" for c in plate)[:20]
        path = os.path.join(tempfile.gettempdir(), f"mtsbu_debug_{prefix}_{safe}_{ts}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
    except Exception:
        pass


def _launch_browser(headless: bool = True, proxy_url: str = None):
    """Launch browser using Patchright (patched Playwright)."""
    from patchright.sync_api import sync_playwright

    pw = sync_playwright().start()
    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--no-first-run",
        "--no-default-browser-check",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-infobars",
        "--window-size=1280,800",
    ]

    launch_kwargs = dict(
        headless=headless,
        args=launch_args,
    )

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
    browser._pw = pw
    return browser


def _try_click_turnstile(page, status_cb=None):
    """
    Try to solve Cloudflare Turnstile by finding its iframe and clicking the checkbox.
    This is a sync fallback for when Turnstile doesn't auto-solve.
    """
    try:
        if status_cb:
            status_cb("🔍", "Пошук Turnstile iframe...")

        # Find Turnstile iframe
        iframe_el = page.query_selector(f'iframe[src*="challenges.cloudflare.com"]')
        if not iframe_el:
            # Also try partial match
            iframe_el = page.query_selector('iframe[src*="turnstile"]')
        if not iframe_el:
            if status_cb:
                status_cb("⚠️", "Turnstile iframe не знайдено")
            return False

        # Get the frame content
        frame = iframe_el.content_frame()
        if not frame:
            if status_cb:
                status_cb("⚠️", "Не вдалося отримати frame Turnstile")
            return False

        if status_cb:
            status_cb("🔍", "Очікування чекбокса Turnstile...")

        # Try to find and click the checkbox input inside the iframe
        checkbox = frame.query_selector('input[type="checkbox"]')
        if checkbox:
            checkbox.click()
            if status_cb:
                status_cb("✅", "Клік по чекбоксу Turnstile")
            return True

        # Try clicking the body/container of the iframe (some Turnstile versions)
        body = frame.query_selector("body")
        if body:
            body.click()
            if status_cb:
                status_cb("✅", "Клік по контейнеру Turnstile")
            return True

        if status_cb:
            status_cb("⚠️", "Чекбокс Turnstile не знайдено в iframe")
        return False

    except Exception as e:
        if status_cb:
            status_cb("⚠️", f"Помилка кліку Turnstile: {e}")
        return False


class MtsbuChecker:
    def __init__(self, headless: bool = False, status_cb: Optional[StatusCallback] = None):
        self.headless = headless
        self.status_cb = status_cb
        self._browser = None
        self.suppress_debug = False  # set True during binary search to silence expected "not found"

    def _status(self, icon: str, message: str):
        if self.status_cb:
            self.status_cb(icon, message)

    def _get_browser(self):
        if self._browser is None:
            self._status("🚀", "Запуск браузера (Patchright)...")
            proxy_url = os.environ.get("PROXY_URL")
            self._browser = _launch_browser(headless=self.headless, proxy_url=proxy_url)
        return self._browser

    def _wait_for_turnstile(self, page):
        """Wait for Cloudflare Turnstile to auto-solve, then try click if needed."""
        self._status("🛡️", "Очікування Cloudflare Turnstile...")

        # Phase 1: Wait for auto-solve (15 seconds)
        for i in range(15):
            solved = page.evaluate("""() => {
                const f = document.querySelector('[name="g-recaptcha-response"]');
                if (f && f.value && f.value.length > 0) return true;
                const f2 = document.querySelector('[name="cf-turnstile-response"]');
                if (f2 && f2.value && f2.value.length > 0) return true;
                return false;
            }""")
            if solved:
                self._status("✅", "Turnstile пройдено (авто)")
                return True
            page.wait_for_timeout(1000)

        # Phase 2: Try clicking the Turnstile checkbox (15 seconds max)
        self._status("🖱️", "Спроба кліку по Turnstile...")
        clicked = _try_click_turnstile(page, self._status)

        if clicked:
            for i in range(15):
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

        self._status("⚠️", "Turnstile не вирішено — подаємо форму все одно")
        return False

    def _submit_and_wait(self, page, query: str):
        self._status("🔍", "Надсилання запиту...")

        # Check if Turnstile token exists (try both field names)
        turnstile_ok = page.evaluate("""() => {
            const f = document.querySelector('[name="g-recaptcha-response"]');
            if (f && f.value && f.value.length > 0) return true;
            const f2 = document.querySelector('[name="cf-turnstile-response"]');
            if (f2 && f2.value && f2.value.length > 0) return true;
            return false;
        }""")

        if not turnstile_ok:
            self._status("⚠️", "Turnstile не вирішено — пробуємо подати форму все одно...")
            # Set dummy tokens to bypass client-side validation
            page.evaluate("""() => {
                const f = document.querySelector('[name="g-recaptcha-response"]');
                if (f) f.value = 'dummy-token';
                const f2 = document.querySelector('[name="cf-turnstile-response"]');
                if (f2) f2.value = 'dummy-token';
            }""")

        # Force-enable submit button
        try:
            submit_btn = page.locator('#submitBtn, button[type="submit"], input[type="submit"]').first
            submit_btn.evaluate("""el => {
                el.disabled = false;
                el.removeAttribute('disabled');
                el.classList.remove('disabled');
            }""")
            page.wait_for_timeout(500)
        except Exception:
            pass

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

            # Primary: URL changed to a result page (not the form page)
            if current_url != original_url:
                # Result pages: /Search/ByRegNo, /Search/ByVin, /Search/ByPolicy, etc.
                # Form page: /Search/Main/ua — should NOT match
                is_result = any(p in current_url for p in ["/Search/ByRegNo", "/Search/ByVin", "/Search/ByPolicy"])
                is_form = "/Search/Main" in current_url
                if is_result:
                    self._status("✅", "Сторінка результату завантажена")
                    return html, current_url
                if is_form:
                    # Form reloaded — server rejected the submission
                    self._status("⚠️", "Сервер повернув сторінку форми")
                    return html, current_url

            # Secondary: check for result indicators (NOT the form page)
            # Look for "not found" or actual result content — but NOT the form itself
            if "#notFound" in html or "not-found" in html.lower():
                return html, current_url

        self._status("⚠️", "Сторінка не змінилась, читаємо поточний HTML")
        html = page.content()
        return html, page.url

    def _check(self, query: str, date: str, tab_selector: str, input_selector: str, date_selector: str, label: str) -> dict:
        browser = self._get_browser()
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="uk-UA",
            timezone_id="Europe/Kyiv",
        )
        page = context.new_page()
        try:
            turnstile_solved = False
            max_attempts = 3

            for attempt in range(max_attempts):
                self._status("🌐", f"Відкриття policy.mtsbu.ua... (спроба {attempt+1}/{max_attempts})")
                page.goto("https://policy.mtsbu.ua/", wait_until="load", timeout=60000)
                page.wait_for_timeout(2000)

                # Switch tab and fill form FIRST (Turnstile only blocks submit button)
                self._status("🔄", f"Вибір вкладки «{label}»...")
                page.evaluate(f"""() => {{
                    const tab = document.querySelector('{tab_selector.split(",")[0].strip()}');
                    if (tab) tab.click();
                }}""")
                page.wait_for_timeout(1000)

                self._status("✏️", f"Заповнення форми: {query}...")
                page.evaluate(f"""([q, d]) => {{
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
                }}""", [query, date])

                # NOW wait for Turnstile (form already filled)
                turnstile_solved = self._wait_for_turnstile(page)

                if turnstile_solved:
                    break

                if attempt < max_attempts - 1:
                    self._status("🔄", f"Повтор завантаження сторінки...")
                    page.wait_for_timeout(2000)

            if not turnstile_solved:
                self._status("⚠️", f"Turnstile не вирішено — продовжуємо все одно")

            html, result_url = self._submit_and_wait(page, query)

            result = parse_result_page(html)
            result["url"] = result_url

            if not result.get("found") and not self.suppress_debug:
                _save_debug_html(html, label[:3], query)
                self._status("⚠️", f"Парсер не знайшов поліс. HTML збережено в {tempfile.gettempdir()}")

            if not self.suppress_debug:
                if result.get("found"):
                    self._status("✅", "Поліс знайдено!")
                else:
                    self._status("❌", "Поліс не знайдено")

            return result

        finally:
            context.close()

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
            tab_selector='a[href="#vinCode"], a#vinCode-tab',
            input_selector="#PolicyVinModel_VinCode",
            date_selector="#vinDate",
            label="За VIN-кодом",
        )

    def check(self, plate: str, date: str) -> dict:
        return self.check_by_plate(plate, date)

    def close(self):
        if self._browser:
            self._status("👋", "Закриття браузера...")
            try:
                pw = getattr(self._browser, "_pw", None)
                self._browser.close()
                if pw:
                    pw.stop()
            except Exception:
                pass
            self._browser = None
