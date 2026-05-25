import customtkinter as ctk


class LogPanel(ctk.CTkScrollableFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._lines = []

    def add_message(self, icon: str, message: str):
        label = ctk.CTkLabel(
            self,
            text=f"{icon}  {message}",
            anchor="w",
            justify="left",
            font=ctk.CTkFont(size=13),
            wraplength=self.winfo_width() - 40 if self.winfo_width() > 40 else 500,
        )
        label.pack(fill="x", padx=8, pady=2, anchor="w")
        self._lines.append(label)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        self.after(10, lambda: self._canvas.yview_moveto(1.0))

    def clear(self):
        for widget in self.winfo_children():
            widget.destroy()
        self._lines.clear()
