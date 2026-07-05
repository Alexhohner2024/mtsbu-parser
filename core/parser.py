import re

from bs4 import BeautifulSoup


def normalize_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).replace("\u00a0", " ").strip()


def _value_by_label(section, label: str):
    headlines = section.find_all("div", class_="headline")
    for h in headlines:
        if normalize_text(h.get_text()) == label:
            v = h.find_next_sibling("div", class_="value")
            if v:
                return normalize_text(v.get_text())
    return None


def _parse_company(soup) -> dict:
    company_data = {}
    company_header = soup.find("h3", string=lambda t: t and "Страхова компанія" in t)
    if company_header:
        section = company_header.parent
        company_data = {
            "name": _value_by_label(section, "Найменування"),
            "status": _value_by_label(section, "Статус страховика"),
            "edrpou": _value_by_label(section, "ЄДРПОУ"),
            "address": None,
            "email": None,
            "phone": None,
        }
        for h in section.find_all("div", class_="headline"):
            text = normalize_text(h.get_text())
            v = h.find_next_sibling("div", class_="value")
            val = normalize_text(v.get_text()) if v else None
            if text.startswith("Місцезнаходження"):
                company_data["address"] = val
            elif text.startswith("Електронна пошта"):
                company_data["email"] = val
            elif text == "Телефон":
                company_data["phone"] = val
    return company_data


def _parse_vehicle(soup) -> dict:
    vehicle_data = {}
    vehicle_header = soup.find("h3", string=lambda t: t and "Транспортний засіб" in t)
    if vehicle_header:
        section = vehicle_header.parent
        make = _value_by_label(section, "Марка") or None
        model = _value_by_label(section, "Модель") or None
        vehicle_data = {
            "type": _value_by_label(section, "Тип"),
            "make": make,
            "model": model,
            "plate": _value_by_label(section, "Реєстраційний номер"),
            "vin": _value_by_label(section, "VIN (номер кузова, шасі, рами)"),
        }
        for h in section.find_all("div", class_="headline"):
            text = normalize_text(h.get_text())
            v = h.find_next_sibling("div", class_="value")
            val = normalize_text(v.get_text()) if v else None
            if "зареєстрований" in text or "зарегістрований" in text:
                vehicle_data["registeredInUkraine"] = val
            if text == "Марка та модель" and val:
                split = val.split(None, 1)
                vehicle_data["make"] = split[0] if split else None
                vehicle_data["modelRaw"] = split[1] if len(split) > 1 else None
    return vehicle_data


def parse_result_page(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    content = soup.find("div", class_="content")
    if not content:
        content = soup.find("main") or soup.find("article") or soup.find("body")

    if not content:
        return {"found": False, "error": "Не знайдено блок результатів"}

    content_text = normalize_text(content.get_text())

    not_found = (
        content.find(id="notFound")
        or content.find("div", class_="not-found")
        or content.find("h3", string=lambda t: t and "поліс не знайдено" in t.lower())
        or content.find("h3", string=lambda t: t and "пошук не дав результатів" in t.lower())
    )
    if not_found:
        # Extract meaningful message from the error block
        msg_el = not_found
        h3 = content.find("h3", string=lambda t: t and "пошук не дав результатів" in t.lower())
        if h3:
            msg_el = h3
        return {"found": False, "message": normalize_text(msg_el.get_text())}

    form = content.find("form")
    if form:
        form.decompose()
        remaining = normalize_text(content.get_text())
        if not remaining or remaining in ("Оберіть критерій пошуку", "Оберіть критерій пошуку:"):
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

    if not result.get("policyNumber"):
        policy_match = re.search(r"Поліс\s*№\s*(\d+)", content_text)
        if policy_match:
            result["policyNumber"] = policy_match.group(1)

    company = _parse_company(content)
    if company:
        result["company"] = company

    vehicle = _parse_vehicle(content)
    if vehicle:
        result["vehicle"] = vehicle

    if not result.get("policyNumber"):
        return {"found": False, "message": "Не вдалося знайти номер полісу"}

    return result
