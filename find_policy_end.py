#!/usr/bin/env python3
"""
Пошук дати закінчення полісу ОСЦПВ за госномером.

Алгоритм:
1. Отримуємо номер поточного полісу
2. Експоненційний пошук назад — знаходимо межу (дата без цього полісу)
3. Бінарний пошук між межами — точна дата початку
4. Кінець = початок + 1 рік - 1 день

Usage:
    python find_policy_end.py ВН1654ОА
    python find_policy_end.py ВН1654ОА --headless
"""

import argparse
import sys
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from check_policy import check_policy


def date_to_str(d: datetime) -> str:
    return d.strftime("%d.%m.%Y")


def str_to_date(s: str) -> datetime:
    return datetime.strptime(s, "%d.%m.%Y")


def fmt_delta(days: int) -> str:
    if days >= 365:
        years = days // 365
        rem = days % 365
        if rem >= 30:
            months = rem // 30
            return f"{years}р {months}міс"
        return f"{years}р"
    if days >= 30:
        months = days // 30
        return f"{months}міс"
    return f"{days}дн"


def check_policy_retry(plate: str, date_str: str, headless: bool, max_retries: int = 2) -> dict:
    for attempt in range(max_retries + 1):
        try:
            return check_policy(plate, date_str, headless=headless)
        except Exception as e:
            if attempt < max_retries:
                print(f"⚠️  помилка: {e}. Повтор {attempt+1}/{max_retries}...")
            else:
                print(f"❌ помилка після {max_retries+1} спроб: {e}")
                return {"found": False, "error": str(e)}


def find_policy_end(plate: str, headless: bool = False):
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    print(f"🔍 Пошук дати закінчення полісу для {plate}")
    print(f"📅 Сьогодні: {date_to_str(today)}")
    print()

    result_today = check_policy_retry(plate, date_to_str(today), headless=headless)
    if not result_today.get("found"):
        print("\n❌ Поліс не знайдено на сьогодні")
        return None, None, None

    policy_number = result_today["policyNumber"]
    print(f"\n📋 Поточний поліс: №{policy_number}")

    print("\n🔎 Експоненційний пошук меж...")
    step = 90
    offset = step
    prev_date = today
    prev_result = result_today

    MAX_STEPS = 20
    for i in range(MAX_STEPS):
        check_date = today - timedelta(days=offset)

        if check_date.year < 2010:
            print("  ⛔ Дійшли до 2010 року — поліс діє дуже довго")
            break

        date_str = date_to_str(check_date)
        print(f"  [{i+1}] Перевірка {date_str} (offset: -{offset}дн)...", end=" ", flush=True)

        result = check_policy_retry(plate, date_str, headless=headless)
        found_policy = result.get("policyNumber")

        if found_policy == policy_number:
            print(f"✅ той же поліс №{found_policy}")
            prev_date = check_date
            prev_result = result
            offset += step
            step *= 2
        else:
            if result.get("found"):
                print(f"⚠️  інший поліс №{found_policy}")
            else:
                print("❌ поліс не знайдено")
            break
    else:
        print("  ⛔ Достигнут лимит шагов")

    print("\n🎯 Бінарний пошук точної дати початку...")
    low = check_date
    high = prev_date

    low_delta = (today - low).days
    high_delta = (today - high).days
    print(f"  Межі: {date_to_str(low)} — {date_to_str(high)} ({low_delta}–{high_delta}дн тому)")

    iterations = 0
    while (high - low).days > 1:
        mid = low + (high - low) // 2
        date_str = date_to_str(mid)
        print(f"  [{iterations+1}] {date_str}...", end=" ", flush=True)

        result = check_policy_retry(plate, date_str, headless=headless)
        found_policy = result.get("policyNumber")

        if found_policy == policy_number:
            high = mid
            print(f"✅ той же поліс (→ зсуваємо HIGH)")
        else:
            low = mid
            if result.get("found"):
                print(f"⚠️  інший поліс №{found_policy} (→ зсуваємо LOW)")
            else:
                print(f"❌ не знайдено (→ зсуваємо LOW)")

        iterations += 1

    start_date = high
    end_date = start_date + relativedelta(years=1) - timedelta(days=1)
    duration = (end_date - today).days
    duration_str = fmt_delta(duration)

    print(f"\n{'=' * 50}")
    print(f"  📋 Результат для {plate}")
    print(f"  Поліс №{policy_number}")
    print(f"  Початок:   {date_to_str(start_date)}")
    print(f"  Закінчення: {date_to_str(end_date)}")
    print(f"  Залишилось: {duration_str} ({duration} днів)")
    print(f"  Перевірок:  {i + 1 + iterations + 1}")
    print(f"{'=' * 50}")

    return policy_number, start_date, end_date


def main():
    parser = argparse.ArgumentParser(description="Пошук дати закінчення полісу ОСЦПВ за госномером")
    parser.add_argument("plate", help="Державний номер ТЗ (напр. ВН1654ОА)")
    parser.add_argument("--headless", action="store_true", help="Запустити браузер без вікна")
    args = parser.parse_args()

    policy_number, start_date, end_date = find_policy_end(args.plate, headless=args.headless)

    return 0 if policy_number else 1


if __name__ == "__main__":
    sys.exit(main())
