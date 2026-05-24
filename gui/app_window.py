import ctypes
import threading

import customtkinter as ctk

from core.finder import find_policy_end
from gui.input_frame import InputFrame
from gui.log_panel import LogPanel
from gui.result_frame import ResultCard


def _try_enable_mica(window):
    try:
        window.update()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        DWMWA_MICA_EFFECT = 1029
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_MICA_EFFECT,
            ctypes.byref(value), ctypes.sizeof(value)
        )
    except Exception:
        pass


class AppWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("MTSBU Parser")
        self.geometry("620x620")
        self.minsize(520, 480)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.attributes("-alpha", 0.97)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1)

        self.input_frame = InputFrame(self, on_search_callback=self._start_search)
        self.input_frame.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))

        log_container = ctk.CTkFrame(self, fg_color=("gray85", "gray17"))
        log_container.grid(row=1, column=0, sticky="ew", padx=12, pady=(4, 4))

        log_label = ctk.CTkLabel(
            log_container,
            text="📋  Процес",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        )
        log_label.pack(fill="x", padx=12, pady=(6, 0))

        self.log_panel = LogPanel(log_container, height=120)
        self.log_panel.pack(fill="x", padx=8, pady=(2, 6))

        self.result_card = ResultCard(self)
        self.result_card.grid(row=2, column=0, sticky="nsew", padx=12, pady=(4, 12))

        self._search_sequence = 0
        self._search_type = "plate"
        self._query = ""

        self.after(100, _try_enable_mica, self)

    def _start_search(self, search_type: str, query: str):
        self._search_type = search_type
        self._query = query
        self._search_sequence += 1
        self._current_seq = self._search_sequence

        self.result_card.clear()
        self.log_panel.clear()
        self.input_frame.search_btn.configure(state="disabled")

        self.log_panel.add_message("🚀", "Запуск перевірки...")

        self.worker_thread = threading.Thread(
            target=self._run_search,
            args=(self._current_seq,),
            daemon=True,
        )
        self.worker_thread.start()

    def _status_cb(self, icon: str, message: str):
        self.after(0, lambda: self.log_panel.add_message(icon, message))

    def _run_search(self, seq: int):
        query = self._query
        search_type = self._search_type
        try:
            self.after(0, lambda q=query: self.log_panel.add_message("🔍", f"Пошук: {q}..."))

            policy_number, start_date, end_date, result = find_policy_end(
                query=query,
                search_type=search_type,
                headless=True,
                status_cb=self._status_cb,
            )

            if seq != self._search_sequence:
                return

            if result:
                self.after(0, lambda r=result, q=query: self._show_result(r, q))
            else:
                self.after(0, lambda: self.log_panel.add_message("❌", "Поліс не знайдено"))

        except Exception as e:
            self.after(0, lambda seq=seq: (
                self.log_panel.add_message("❌", f"Помилка: {e}") if seq == self._search_sequence else None
            ))
        finally:
            self.after(0, lambda seq=seq: (
                self.input_frame.enable_search() if seq == self._search_sequence else None
            ))

    def _show_result(self, result: dict, query: str):
        self.result_card.show_result(result, query)

    def run(self):
        self.mainloop()
