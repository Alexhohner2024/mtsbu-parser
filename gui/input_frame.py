import pyperclip
import customtkinter as ctk


class InputFrame(ctk.CTkFrame):
    def __init__(self, master, on_search_callback, **kwargs):
        super().__init__(master, **kwargs)
        self.on_search = on_search_callback
        self.search_type = ctk.StringVar(value="plate")

        title = ctk.CTkLabel(
            self,
            text="MTSBU Parser",
            font=ctk.CTkFont(size=22, weight="bold"),
            anchor="w",
        )
        title.pack(fill="x", padx=20, pady=(16, 0))

        subtitle = ctk.CTkLabel(
            self,
            text="Перевірка полісу ОСЦПВ через policy.mtsbu.ua",
            font=ctk.CTkFont(size=13),
            text_color=("gray40", "gray60"),
            anchor="w",
        )
        subtitle.pack(fill="x", padx=20, pady=(0, 12))

        radio_frame = ctk.CTkFrame(self, fg_color="transparent")
        radio_frame.pack(fill="x", padx=20, pady=(0, 8))

        plate_radio = ctk.CTkRadioButton(
            radio_frame,
            text="За госномером",
            variable=self.search_type,
            value="plate",
            font=ctk.CTkFont(size=14),
        )
        plate_radio.pack(side="left", padx=(0, 16))

        vin_radio = ctk.CTkRadioButton(
            radio_frame,
            text="За VIN-кодом",
            variable=self.search_type,
            value="vin",
            font=ctk.CTkFont(size=14),
        )
        vin_radio.pack(side="left")

        input_row = ctk.CTkFrame(self, fg_color="transparent")
        input_row.pack(fill="x", padx=20, pady=(0, 8))
        input_row.grid_columnconfigure(0, weight=1)

        self.input_var = ctk.StringVar()

        self.input_entry = ctk.CTkEntry(
            input_row,
            textvariable=self.input_var,
            placeholder_text="ВН1654ОА",
            font=ctk.CTkFont(size=16),
            height=44,
        )
        self.input_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        paste_btn = ctk.CTkButton(
            input_row,
            text="📋",
            font=ctk.CTkFont(size=16),
            width=44,
            height=44,
            command=self._paste_from_clipboard,
        )
        paste_btn.grid(row=0, column=1, padx=(0, 0))

        self.after(100, self._bind_inner_entry)
        self.input_entry.bind("<<Paste>>", self._on_ctrl_v, add="+")
        self.input_entry.bind("<Button-3>", self._show_context_menu)

        self.hint_label = ctk.CTkLabel(
            self,
            text="Формат: АА1234ВС (укр. літери)",
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray50"),
            anchor="w",
        )
        self.hint_label.pack(fill="x", padx=20, pady=(0, 12))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 16))

        self.search_btn = ctk.CTkButton(
            btn_frame,
            text="🔍  Знайти",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=42,
            command=self._on_search_click,
        )
        self.search_btn.pack(fill="x")

        self.search_type.trace_add("write", self._on_type_change)

    def _bind_inner_entry(self):
        try:
            inner = self.input_entry._entry
            inner.bind("<Control-v>", self._on_ctrl_v)
        except AttributeError:
            self.input_entry.bind("<Control-v>", self._on_ctrl_v, add="+")

    def _paste_from_clipboard(self) -> bool:
        try:
            text = pyperclip.paste()
            if text:
                self.input_var.set(text.strip())
                self.after(10, lambda: self.input_entry.icursor("end"))
                return True
        except Exception:
            pass
        return False

    def _on_ctrl_v(self, event=None):
        if self._paste_from_clipboard():
            return "break"

    def _show_context_menu(self, event):
        menu = ctk.CTkToplevel(self)
        menu.geometry(f"+{event.x_root}+{event.y_root}")
        menu.overrideredirect(True)
        menu.attributes("-topmost", True)

        btn = ctk.CTkButton(
            menu,
            text="📋  Вставити",
            font=ctk.CTkFont(size=13),
            height=32,
            command=lambda: (self._paste_from_clipboard(), menu.destroy()),
        )
        btn.pack(padx=2, pady=2)

        menu.focus()
        menu.bind("<FocusOut>", lambda e: menu.destroy())

    def _on_type_change(self, *_):
        if self.search_type.get() == "plate":
            self.input_entry.configure(placeholder_text="ВН1654ОА")
            self.hint_label.configure(text="Формат: АА1234ВС (укр. літери)")
        else:
            self.input_entry.configure(placeholder_text="JTD...")
            self.hint_label.configure(text="VIN-код: 17 символів (цифри та латин. літери)")

    def _on_search_click(self):
        query = self.input_var.get().strip()
        if not query:
            self.input_entry.configure(border_color="red")
            self.after(2000, lambda: self.input_entry.configure(border_color=("gray60", "gray30")))
            return
        self.search_btn.configure(state="disabled")
        self.on_search(self.search_type.get(), query)

    def enable_search(self):
        self.search_btn.configure(state="normal")

    def set_input(self, text: str):
        self.input_var.set(text)
