import pyperclip

import customtkinter as ctk

from core.finder import fmt_delta

FIELD_ICONS = {
    "policyNumber": "🆔",
    "url": "🔗",
    "status": "📌",
    "statusDate": "📅",
}

COMPANY_ICONS = {
    "name": "🏢",
    "status": "📌",
    "edrpou": "🔢",
    "address": "📍",
    "phone": "📞",
    "email": "📧",
}

VEHICLE_ICONS = {
    "type": "📂",
    "make": "🚗",
    "model": "🚗",
    "plate": "🔢",
    "vin": "🔍",
}


def _fmt_label(icon: str, label: str, value: str) -> str:
    return f"{icon}  {label}: {value}"


class ResultCard(ctk.CTkScrollableFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._labels = []

    def show_result(self, result: dict, query: str):
        self.clear()

        header = ctk.CTkLabel(
            self,
            text="✅  Результат пошуку",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        )
        header.pack(fill="x", padx=16, pady=(12, 4))
        self._labels.append(header)

        sep = ctk.CTkFrame(self, height=2, fg_color=("gray70", "gray30"))
        sep.pack(fill="x", padx=16, pady=(0, 8))
        self._labels.append(sep)

        if result.get("policyNumber"):
            self._add_field("🆔", "Поліс", f"№{result['policyNumber']}")

        if result.get("url"):
            self._add_field("🔗", "Посилання", result["url"])

        if result.get("status"):
            self._add_field("📌", "Статус", result["status"])

        if result.get("statusDate"):
            self._add_field("📅", "Дата статусу", result["statusDate"])

        company = result.get("company")
        if company:
            sub = ctk.CTkLabel(
                self,
                text="🏢  Страхова компанія",
                font=ctk.CTkFont(size=14, weight="bold"),
                anchor="w",
            )
            sub.pack(fill="x", padx=16, pady=(8, 2))
            self._labels.append(sub)

            for key, label in [
                ("name", "Назва"),
                ("status", "Статус"),
                ("edrpou", "ЄДРПОУ"),
                ("address", "Адреса"),
                ("phone", "Телефон"),
                ("email", "Email"),
            ]:
                val = company.get(key)
                if val:
                    self._add_field(COMPANY_ICONS.get(key, "•"), label, val)

        vehicle = result.get("vehicle")
        if vehicle:
            sub = ctk.CTkLabel(
                self,
                text="🚗  Транспортний засіб",
                font=ctk.CTkFont(size=14, weight="bold"),
                anchor="w",
            )
            sub.pack(fill="x", padx=16, pady=(8, 2))
            self._labels.append(sub)

            for key, label in [
                ("type", "Тип"),
                ("make", "Марка"),
                ("model", "Модель"),
                ("plate", "Госномер"),
                ("vin", "VIN"),
            ]:
                val = vehicle.get(key)
                if val:
                    self._add_field(VEHICLE_ICONS.get(key, "•"), label, val)

        if result.get("start_date") and result.get("end_date"):
            sep2 = ctk.CTkFrame(self, height=2, fg_color=("gray70", "gray30"))
            sep2.pack(fill="x", padx=16, pady=8)
            self._labels.append(sep2)

            self._add_field("📅", "Початок", result["start_date"])
            self._add_field("⏳", "Закінчення", result["end_date"])
            remaining = result.get("remaining_str") or result.get("remaining_days")
            if remaining:
                self._add_field("⏰", "Залишилось", str(remaining))

            total = result.get("checks_total")
            if total:
                self._add_field("📊", "Перевірок", str(total))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=(12, 16))

        copy_btn = ctk.CTkButton(
            btn_frame,
            text="📋  Копіювати все",
            command=lambda: self._copy_result(result, query),
            width=160,
            height=36,
        )
        copy_btn.pack(side="left", padx=(0, 8))

    def _add_field(self, icon: str, label: str, value: str):
        text = f"{icon}  {label}: {value}"
        w = self.winfo_width()
        wraplength = max(w - 80, 300) if w > 80 else 500
        lbl = ctk.CTkLabel(
            self,
            text=text,
            anchor="w",
            justify="left",
            font=ctk.CTkFont(size=13),
            wraplength=wraplength,
        )
        lbl.pack(fill="x", padx=16, pady=1)
        self._labels.append(lbl)

    def _copy_result(self, result: dict, query: str):
        lines = ["📋 Результат перевірки полісу ОСЦПВ", f"🔍 Запит: {query}", ""]

        if result.get("policyNumber"):
            lines.append(f"🆔 Поліс: №{result['policyNumber']}")
        if result.get("url"):
            lines.append(f"🔗 Посилання: {result['url']}")
        if result.get("status"):
            lines.append(f"📌 Статус: {result['status']}")
        if result.get("statusDate"):
            lines.append(f"📅 Дата статусу: {result['statusDate']}")

        company = result.get("company")
        if company:
            lines.append("")
            lines.append("🏢 Страхова компанія:")
            for key, label in [
                ("name", "Назва"),
                ("status", "Статус"),
                ("edrpou", "ЄДРПОУ"),
                ("address", "Адреса"),
                ("phone", "Телефон"),
                ("email", "Email"),
            ]:
                val = company.get(key)
                if val:
                    lines.append(f"  {label}: {val}")

        vehicle = result.get("vehicle")
        if vehicle:
            lines.append("")
            lines.append("🚗 Транспортний засіб:")
            for key, label in [
                ("type", "Тип"),
                ("make", "Марка"),
                ("model", "Модель"),
                ("plate", "Госномер"),
                ("vin", "VIN"),
            ]:
                val = vehicle.get(key)
                if val:
                    lines.append(f"  {label}: {val}")

        if result.get("start_date") and result.get("end_date"):
            lines.append("")
            lines.append(f"📅 Початок: {result['start_date']}")
            lines.append(f"⏳ Закінчення: {result['end_date']}")
            remaining = result.get("remaining_str") or result.get("remaining_days")
            if remaining:
                lines.append(f"⏰ Залишилось: {remaining}")
            total = result.get("checks_total")
            if total:
                lines.append(f"📊 Перевірок: {total}")

        full_text = "\n".join(lines)
        try:
            pyperclip.copy(full_text)
            self._show_toast("Скопійовано!")
        except Exception:
            self._show_toast("Не вдалося скопіювати")

    def _show_toast(self, message: str):
        toast = ctk.CTkToplevel(self)
        toast.geometry("260x60+{}+{}".format(
            self.winfo_rootx() + self.winfo_width() // 2 - 130,
            self.winfo_rooty() + self.winfo_height() // 2 - 30,
        ))
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(fg_color=("gray90", "gray20"))

        label = ctk.CTkLabel(
            toast,
            text=message,
            font=ctk.CTkFont(size=14),
            anchor="center",
        )
        label.pack(expand=True, fill="both")

        toast.after(1500, toast.destroy)

    def clear(self):
        for widget in self.winfo_children():
            widget.destroy()
        self._labels.clear()
