#!/usr/bin/env python3
"""
MTSBU Policy Checker — CLI
Перевірка страхового полісу за державним номером через policy.mtsbu.ua

Usage:
    python check_policy.py AA1234BC
    python check_policy.py AA1234BC --date 16.05.2026
    python check_policy.py AA1234BC --json output.json
    python check_policy.py --vin JTD... --date 16.05.2026
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from core.checker import MtsbuChecker


def print_result(result: dict, query: str, date: str):
    print("\n" + "=" * 50)
    print("  Перевірка полісу ОСЦПВВТЗ")
    print(f"  Запит: {query}")
    print(f"  Дата: {date}")
    print("=" * 50)

    if result.get("error"):
        print(f"\n  ❌ Помилка: {result['error']}")
        print()
        return

    if not result.get("found"):
        print("\n  ❌ Поліс не знайдено")
        if result.get("message"):
            print(f"  {result['message']}")
        print()
        return

    print("\n  ✅ Поліс знайдено")
    if result.get("policyNumber"):
        print(f"  🆔 Номер: {result['policyNumber']}")
    if result.get("url"):
        print(f"  🔗 Посилання: {result['url']}")
    if result.get("status"):
        print(f"  📌 Статус: {result['status']}")
    if result.get("statusDate"):
        print(f"  📅 Дата: {result['statusDate']}")

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


def check_policy(query: str, date: str, search_type: str = "plate") -> dict:
    checker = MtsbuChecker(headless=False)  # Patchright needs headless=False for Turnstile
    try:
        if search_type == "vin":
            return checker.check_by_vin(query, date)
        return checker.check_by_plate(query, date)
    finally:
        checker.close()


def main():
    parser = argparse.ArgumentParser(description="Перевірка полісу ОСЦПВВТЗ за державним номером або VIN")
    parser.add_argument("query", nargs="?", help="Державний номер (напр. AA1234BC) або VIN-код")
    parser.add_argument("--date", default=None, help="Дата у форматі дд.мм.рррр (за замовчуванням сьогодні)")
    parser.add_argument("--headless", action="store_true", default=True, help=argparse.SUPPRESS)
    parser.add_argument("--json", dest="json_file", help="Зберегти результат у JSON файл")
    parser.add_argument("--vin", action="store_true", help="Пошук за VIN-кодом")

    args = parser.parse_args()

    if not args.query:
        parser.print_help()
        return 1

    if args.date is None:
        args.date = datetime.now().strftime("%d.%m.%Y")

    search_type = "vin" if args.vin else "plate"
    label = "VIN" if args.vin else "госномер"

    print(f"\n🔍 Перевірка {args.query} ({label}) на {args.date}")

    result = check_policy(args.query, args.date, search_type=search_type)

    print_result(result, args.query, args.date)

    if args.json_file:
        output = {
            "query": args.query,
            "search_type": search_type,
            "date": args.date,
            "checked_at": datetime.now().isoformat(),
            **result,
        }
        Path(args.json_file).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  💾 Результат збережено: {args.json_file}")

    return 0 if result.get("found") else (2 if result.get("error") else 1)


if __name__ == "__main__":
    sys.exit(main())
