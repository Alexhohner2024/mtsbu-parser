#!/usr/bin/env python3
"""
MTSBU Policy Checker
Перевірка страхового полісу за державним номером через policy.mtsbu.ua
Використовує CloakBrowser для обходу Cloudflare Turnstile.

Usage:
    python check_policy.py AA1234BC
    python check_policy.py AA1234BC --date 16.05.2026
    python check_policy.py AA1234BC --json output.json
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from cloakbrowser import launch
from bs4 import BeautifulSoup


def normalize_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).replace("\u00a0", " ").strip()


def parse_result_page(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    content = soup.find("div", class_="content")
    if not content:
        return {"found": False, "error": "Не знайдено блок результатів"}

    not_found = (
        content.find(id="notFound")
        or content.find("div", class_="not-found")
        or content.find("h3", string=lambda t: t and "поліс не знайдено" in t.lower())
    )
    if not_found:
        return {"found": False, "message": normalize_text(not_found.get_text())}

    form = content.find("form")
    if form:
        form.decompose()
        remaining = normalize_text(content.get_text())
        if not remaining or remaining == "Оберіть критерій пошуку":
            return {"found": False, "message": "Поліс не знайдено"}

    result = {"found": True}

    title_block = content.find("div", class_="title")
    if title_block:
        title_text = normalize_text(title_block.get_text())
        policy_match = re.search(r"Поліс\s*№\s*(\d+)", title_text)
        if policy_match:
            result["policyNumber"] = policy_match.group(1)

        status_label = title_block.find("div", class_="label")
        if status_label:
            result["status"] = normalize_text(status_label.get_text())

    date_el = content.find("div", class_="date")
    if date_el:
        result["statusDate"] = normalize_text(date_el.get_text()).replace("на ", "", 1)

    def value_by_label(section, label: str):
        headlines = section.find_all("div", class_="headline")
        for h in headlines:
            if normalize_text(h.get_text()) == label:
                v = h.find_next_sibling("div", class_="value")
                if v:
                    return normalize_text(v.get_text())
        return None

    company_header = content.find("h3", string=lambda t: t and "Страхова компанія" in t)
    if company_header:
        section = company_header.parent
        company_data = {
            "name": value_by_label(section, "Найменування"),
            "status": value_by_label(section, "Статус страховика"),
            "edrpou": value_by_label(section, "ЄДРПОУ"),
            "address": None,
            "email": None,
            "phone": None,
        }

        for h in section.find_all("div", class_="headline"):
            text = normalize_text(h.get_text())
            if text.startswith("Місцезнаходження"):
                v = h.find_next_sibling("div", class_="value")
                if v:
                    company_data["address"] = normalize_text(v.get_text())
            if text.startswith("Електронна пошта"):
                v = h.find_next_sibling("div", class_="value")
                if v:
                    company_data["email"] = normalize_text(v.get_text())
            if text == "Телефон":
                v = h.find_next_sibling("div", class_="value")
                if v:
                    company_data["phone"] = normalize_text(v.get_text())

        result["company"] = company_data

    vehicle_header = content.find("h3", string=lambda t: t and "Транспортний засіб" in t)
    if vehicle_header:
        section = vehicle_header.parent
        vehicle_data = {
            "type": value_by_label(section, "Тип"),
            "make": value_by_label(section, "Марка") or None,
            "model": value_by_label(section, "Модель") or None,
            "plate": value_by_label(section, "Реєстраційний номер"),
            "vin": value_by_label(section, "VIN (номер кузова, шасі, рами)"),
        }

        for h in section.find_all("div", class_="headline"):
            text = normalize_text(h.get_text())
            if "зареєстрований" in text or "зарегістрований" in text:
                v = h.find_next_sibling("div", class_="value")
                if v:
                    vehicle_data["registeredInUkraine"] = normalize_text(v.get_text())
            if text == "Марка та модель":
                v = h.find_next_sibling("div", class_="value")
                if v:
                    val = normalize_text(v.get_text())
                    split = val.split(None, 1)
                    vehicle_data["make"] = split[0] if split else None
                    vehicle_data["modelRaw"] = split[1] if len(split) > 1 else None

        result["vehicle"] = vehicle_data

    return result


class MtsbuChecker:
    def __init__(self, headless: bool = False):
        self.browser = launch(
            headless=headless,
            humanize=True,
            args=["--fingerprint=12345"],
        )

    def check(self, plate: str, date: str) -> dict:
        page = self.browser.new_page()
        try:
            page.goto("https://policy.mtsbu.ua/", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)

            plate_tab = page.locator('a[href="#carNumber"], a#carNumber-tab').first
            if plate_tab.is_visible():
                plate_tab.click()
                page.wait_for_timeout(500)

            plate_input = page.locator("#RegNoModel_PlateNumber").first
            plate_input.fill(plate)

            date_input = page.locator("#numDate").first
            date_input.fill(date)

            submit_btn = page.locator('button[type="submit"], input[type="submit"]').first
            submit_btn.wait_for(state="visible", timeout=30000)
            page.wait_for_function("""
                () => {
                    const btn = document.querySelector('button[type=submit], input[type=submit]');
                    return btn && !btn.disabled;
                }
            """, timeout=60000)

            submit_btn.click()
            page.wait_for_timeout(5000)
            page.wait_for_load_state("domcontentloaded", timeout=30000)

            html = page.content()
            return parse_result_page(html)

        finally:
            page.close()

    def close(self):
        self.browser.close()


def print_result(result: dict, plate: str, date: str):
    print("\n" + "=" * 50)
    print("  Перевірка полісу ОСЦПВВТЗ")
    print(f"  Госномер: {plate}")
    print(f"  Дата: {date}")
    print("=" * 50)

    if not result.get("found"):
        print("\n  ❌ Поліс не знайдено")
        if result.get("message"):
            print(f"  {result['message']}")
        print()
        return

    print("\n  ✅ Поліс знайдено")
    print(f"  Номер: {result.get('policyNumber', 'N/A')}")
    print(f"  Статус: {result.get('status', 'N/A')}")
    print(f"  Дата: {result.get('statusDate', 'N/A')}")

    company = result.get("company")
    if company:
        print("\n  🏢 Страхова компанія:")
        print(f"    Назва: {company.get('name', 'N/A')}")
        print(f"    Статус: {company.get('status', 'N/A')}")
        print(f"    ЄДРПОУ: {company.get('edrpou', 'N/A')}")
        if company.get("address"):
            print(f"    Адреса: {company['address']}")
        if company.get("phone"):
            print(f"    Телефон: {company['phone']}")
        if company.get("email"):
            print(f"    Email: {company['email']}")

    vehicle = result.get("vehicle")
    if vehicle:
        print("\n  🚗 Транспортний засіб:")
        print(f"    Тип: {vehicle.get('type', 'N/A')}")
        print(f"    Марка: {vehicle.get('make', 'N/A')}")
        print(f"    Модель: {vehicle.get('model', 'N/A')}")
        print(f"    Госномер: {vehicle.get('plate', 'N/A')}")
        print(f"    VIN: {vehicle.get('vin', 'N/A')}")

    print()


def check_policy(plate: str, date: str, headless: bool = False) -> dict:
    checker = MtsbuChecker(headless=headless)
    try:
        return checker.check(plate, date)
    finally:
        checker.close()


def main():
    parser = argparse.ArgumentParser(description="Перевірка полісу ОСЦПВВТЗ за державним номером")
    parser.add_argument("plate", help="Державний номер ТЗ (напр. AA1234BC)")
    parser.add_argument("--date", default=None, help="Дата у форматі дд.мм.рррр (за замовчуванням сьогодні)")
    parser.add_argument("--headless", action="store_true", help="Запустити браузер без вікна")
    parser.add_argument("--json", dest="json_file", help="Зберегти результат у JSON файл")

    args = parser.parse_args()

    if args.date is None:
        args.date = datetime.now().strftime("%d.%m.%Y")

    print(f"\n🔍 Перевірка: {args.plate} на {args.date}")

    result = check_policy(args.plate, args.date, headless=args.headless)

    print_result(result, args.plate, args.date)

    if args.json_file:
        output = {
            "plate": args.plate,
            "date": args.date,
            "checked_at": datetime.now().isoformat(),
            **result,
        }
        Path(args.json_file).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  💾 Результат збережено: {args.json_file}")

    return 0 if result.get("found") else 1


if __name__ == "__main__":
    sys.exit(main())
