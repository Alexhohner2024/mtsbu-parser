import pyperclip
import customtkinter as ctk


class ResultCard(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._result_data = None
        self._query = None

    def _format_result(self, result: dict, query: str) -> str:
        expired = result.get("expired", False)
        lines = [f"🔍 Запит: {query}", ""]

        if result.get("policyNumber"):
            lines.append(f"🆔 Поліс: №{result['policyNumber']}")
        if result.get("status"):
            lines.append(f"📌 Статус: {result['status']}")

        vehicle = result.get("vehicle")
        if vehicle:
            lines.append("")
            parts = []
            if vehicle.get("make"):
                parts.append(vehicle["make"])
            if vehicle.get("model"):
                parts.append(vehicle["model"])
            lines.append(f"🚗 Авто: {' '.join(parts) if parts else 'N/A'}")
            if vehicle.get("plate"):
                lines.append(f"🔢 Госномер: {vehicle['plate']}")
            if vehicle.get("vin"):
                lines.append(f"🔍 VIN: {vehicle['vin']}")

        company = result.get("company")
        if company and company.get("name"):
            lines.append("")
            parts = [f"🏢 {company['name']}"]
            if company.get("edrpou"):
                parts.append(f"(ЄДРПОУ {company['edrpou']})")
            lines.append(" ".join(parts))

        if result.get("end_date"):
            lines.append("")
            if result.get("start_date"):
                lines.append(f"📅 Початок: {result['start_date']}")
            lines.append(f"⏳ Закінчення: {result['end_date']}")
            if expired:
                overdue = result.get("overdue_str") or result.get("overdue_days")
                if overdue:
                    lines.append(f"🚨 Прострочено: {overdue}")
            else:
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

        expired = result.get("expired", False)
        header = ctk.CTkLabel(
            self,
            text="⚠️  Поліс прострочений" if expired else "✅  Результат пошуку",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=("orange", "#FFA500") if expired else ("gray10", "gray90"),
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
        # Block only printable input (not control shortcuts like Ctrl+C)
        self.textbox.bind("<Key>", lambda e: "break" if e.char and e.char.isprintable() else None)
        self.textbox.bind("<Control-c>", self._copy_selection)
        self.textbox.bind("<Control-C>", self._copy_selection)
        self.textbox.bind("<Button-3>", self._show_context_menu)

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

    def _show_context_menu(self, event):
        import tkinter as tk
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Копіювати виділене", command=self._copy_selection)
        menu.add_command(label="Копіювати все", command=self._copy_all)
        menu.tk_popup(event.x_root, event.y_root)

    def _copy_selection(self, event=None):
        try:
            selected = self.textbox.selection_get()
            root = self.winfo_toplevel()
            root.clipboard_clear()
            root.clipboard_append(selected)
        except Exception:
            pass
        return "break"

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
