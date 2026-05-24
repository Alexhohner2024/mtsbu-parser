#!/usr/bin/env python3
"""
MTSBU Parser — Windows GUI Application
Перевірка полісу ОСЦПВ через policy.mtsbu.ua
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.app_window import AppWindow


def main():
    app = AppWindow()
    app.run()


if __name__ == "__main__":
    main()
