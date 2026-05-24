#!/usr/bin/env python3
"""
Пошук дати закінчення полісу ОСЦПВ за госномером або VIN — CLI.

Usage:
    python find_policy_end.py ВН1654ОА
    python find_policy_end.py --vin JTD...
"""

import argparse
import sys

from core.finder import find_policy_end, date_to_str


def main():
    parser = argparse.ArgumentParser(description="Пошук дати закінчення полісу ОСЦПВ за госномером або VIN")
    parser.add_argument("query", nargs="?", help="Державний номер або VIN-код")
    parser.add_argument("--vin", action="store_true", help="Пошук за VIN-кодом")

    args = parser.parse_args()

    if not args.query:
        parser.print_help()
        return 1

    search_type = "vin" if args.vin else "plate"

    policy_number, start_date, end_date, info = find_policy_end(
        args.query,
        search_type=search_type,
        headless=True,
    )

    if not policy_number:
        print("\n❌ Поліс не знайдено")
        return 1

    company = info.get("company", {})
    vehicle = info.get("vehicle", {})
    vehicle_model = vehicle.get("model") or vehicle.get("modelRaw") or ""

    print(f"\n{'=' * 50}")
    print(f"  📋 Результат для {args.query}")
    print(f"  🆔 Поліс №{policy_number}")
    if info.get("url"):
        print(f"  🔗 Посилання: {info['url']}")
    print(f"  🏢 СК: {company.get('name', 'N/A')}")
    print(f"  🚗 Авто: {vehicle.get('make', '')} {vehicle_model}")
    print(f"  📂 Тип: {vehicle.get('type', 'N/A')}")
    print(f"  🔢 Госномер: {vehicle.get('plate', args.query)}")
    print(f"  🔍 VIN: {vehicle.get('vin', 'N/A')}")
    print(f"  📅 Початок:   {date_to_str(start_date)}")
    print(f"  ⏳ Закінчення: {date_to_str(end_date)}")
    print(f"  ⏰ Залишилось: {info.get('remaining_str', 'N/A')}")
    total = info.get("checks_total", "?")
    print(f"  📊 Перевірок: {total}")
    print(f"{'=' * 50}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
