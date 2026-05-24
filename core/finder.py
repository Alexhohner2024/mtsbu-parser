from datetime import datetime, timedelta
from typing import Callable, Optional, Tuple

from dateutil.relativedelta import relativedelta

from core.checker import MtsbuChecker

StatusCallback = Callable[[str, str], None]


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


def check_with_retry(
    checker: MtsbuChecker,
    search_type: str,
    query: str,
    date_str: str,
    max_retries: int = 2,
) -> dict:
    for attempt in range(max_retries + 1):
        try:
            if search_type == "vin":
                return checker.check_by_vin(query, date_str)
            return checker.check_by_plate(query, date_str)
        except Exception as e:
            if attempt < max_retries:
                checker._status("⚠️", f"Помилка: {e}. Повтор {attempt+1}/{max_retries}...")
            else:
                checker._status("❌", f"Помилка після {max_retries+1} спроб: {e}")
                return {"found": False, "error": str(e)}


def find_policy_end(
    query: str,
    search_type: str = "plate",
    headless: bool = False,
    status_cb: Optional[StatusCallback] = None,
) -> Tuple[Optional[str], Optional[datetime], Optional[datetime], Optional[dict]]:
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    checker = MtsbuChecker(headless=headless, status_cb=status_cb)
    try:
        checker._status("📅", f"Перевірка на {date_to_str(today)}...")

        result_today = check_with_retry(checker, search_type, query, date_to_str(today))
        if not result_today.get("found"):
            checker._status("❌", "Поліс не знайдено на сьогодні")
            return None, None, None, None

        policy_number = result_today["policyNumber"]
        checker._status("📋", f"Поточний поліс: №{policy_number}")

        checker._status("🔎", "Експоненційний пошук меж...")
        step = 180
        offset = step
        prev_date = today

        for i in range(20):
            check_date = today - timedelta(days=offset)
            if check_date.year < 2010:
                checker._status("⛔", "Дійшли до 2010 року — поліс діє дуже довго")
                break

            date_str = date_to_str(check_date)
            msg = f"[{i+1}] Перевірка {date_str} (offset: -{offset}дн)"
            checker._status("🔍", msg)

            result = check_with_retry(checker, search_type, query, date_str)
            found_policy = result.get("policyNumber")

            if found_policy == policy_number:
                checker._status("✅", f"Той же поліс №{found_policy}")
                prev_date = check_date
                offset += step
                step *= 2
            else:
                if result.get("found"):
                    checker._status("⚠️", f"Інший поліс №{found_policy}")
                else:
                    checker._status("❌", "Поліс не знайдено")
                break
        else:
            checker._status("⛔", "Достигнут лимит шагов")

        checker._status("🎯", "Бінарний пошук точної дати початку...")
        low = check_date
        high = prev_date

        low_delta = (today - low).days
        high_delta = (today - high).days
        checker._status("📐", f"Межі: {date_to_str(low)} — {date_to_str(high)} ({low_delta}–{high_delta}дн тому)")

        iterations = 0
        low_ord = low.toordinal()
        high_ord = high.toordinal()

        while high_ord - low_ord > 1:
            mid_ord = (low_ord + high_ord) // 2
            mid = datetime.fromordinal(mid_ord)
            date_str = date_to_str(mid)
            msg = f"[{iterations+1}] {date_str}..."
            checker._status("🎯", msg)

            result = check_with_retry(checker, search_type, query, date_str)
            found_policy = result.get("policyNumber")

            if found_policy == policy_number:
                high_ord = mid_ord
                checker._status("✅", "Той же поліс (→ зсуваємо HIGH)")
            else:
                low_ord = mid_ord
                if result.get("found"):
                    checker._status("⚠️", f"Інший поліс №{found_policy} (→ зсуваємо LOW)")
                else:
                    checker._status("❌", "Не знайдено (→ зсуваємо LOW)")

            iterations += 1

        start_date = datetime.fromordinal(high_ord)
        end_date = start_date + relativedelta(years=1) - timedelta(days=1)

        result_today["start_date"] = date_to_str(start_date)
        result_today["end_date"] = date_to_str(end_date)
        result_today["remaining_days"] = (end_date - today).days
        result_today["remaining_str"] = fmt_delta((end_date - today).days)
        result_today["checks_total"] = i + 1 + iterations + 1

        checker._status("✅", "Пошук завершено!")

        return policy_number, start_date, end_date, result_today

    finally:
        checker.close()
