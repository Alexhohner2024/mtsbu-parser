import pyperclip
import customtkinter as ctk


class ResultCard(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._result_data = None
        self._query = None

    def _format_result(self, result: dict, query: str) -> str:
        lines = [f"🔍 Запит: {query}", ""]

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

        return "\n".join(lines)

    def show_result(self, result: dict, query: str):
        self.clear()
        self._result_data = result
        self._query = query

        header = ctk.CTkLabel(
            self,
            text="✅  Результат пошуку",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        )
        header.pack(fill="x", padx=16, pady=(12, 4))

        sep = ctk.CTkFrame(self, height=2, fg_color=("gray70", "gray30"))
        sep.pack(fill="x", padx=16, pady=(0, 8))

        text_content = self._format_result(result, query)
        self.textbox = ctk.CTkTextbox(
            self,
            wrap="word",
            font=ctk.CTkFont(size=13),
            activate_scrollbars=True,
        )
        self.textbox.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        self.textbox.configure(state="normal")
        self.textbox.insert("0.0", text_content)
        self.textbox.configure(state="disabled")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=(0, 16))

        copy_btn = ctk.CTkButton(
            btn_frame,
            text="📋  Копіювати все",
            command=self._copy_all,
            width=160,
            height=36,
        )
        copy_btn.pack(side="left", padx=(0, 8))

    def _copy_all(self):
        if not self._result_data:
            return
        full_text = self._format_result(self._result_data, self._query or "")
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
        self._result_data = None
        self._query = None
