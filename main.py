"""
SkillProof — Điểm vào chính của ứng dụng.

Chạy: python main.py
"""

import sys
import os
import logging

# ── Đảm bảo thư mục gốc dự án trong sys.path ─────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore    import Qt

from app.utils.constants  import APP_NAME, APP_VERSION, DATA_DIR
from app.utils.helpers    import setup_logging, ensure_dir
from app.utils.styles     import GLOBAL_STYLE
from app.database         import create_all_tables
from app.ui.main_window   import MainWindow


def main() -> int:
    # ── Khởi tạo logging ─────────────────────────────────────────────────────
    log_dir = os.path.join(BASE_DIR, "data", "logs")
    setup_logging(log_dir)
    logger = logging.getLogger(__name__)
    logger.info("Khởi động %s v%s", APP_NAME, APP_VERSION)

    # ── Khởi tạo CSDL ────────────────────────────────────────────────────────
    ensure_dir(DATA_DIR)
    try:
        create_all_tables()
        logger.info("CSDL sẵn sàng.")
    except Exception as exc:
        logger.critical("Không thể khởi tạo CSDL: %s", exc)
        return 1

    # ── Khởi tạo ứng dụng Qt ─────────────────────────────────────────────────
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    # Bật High-DPI (mặc định trong Qt6, giữ lại để tương thích rõ ràng)
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    # Áp dụng stylesheet toàn cục
    app.setStyleSheet(GLOBAL_STYLE)

    # ── Khởi tạo cửa sổ chính ────────────────────────────────────────────────
    window = MainWindow()
    window.show()

    logger.info("Ứng dụng đang chạy.")
    exit_code = app.exec()

    logger.info("Ứng dụng kết thúc với mã: %d", exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
