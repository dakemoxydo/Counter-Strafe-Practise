import logging
import signal

import customtkinter as ctk

from config import Config
from dashboard import Dashboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Starting cStrafe UI...")
    config = Config()

    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")

    app = Dashboard(config)

    # Graceful shutdown on Ctrl+C
    def on_signal(sig, frame):
        logger.info("Received shutdown signal, cleaning up...")
        app.on_closing()

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    logger.info("cStrafe UI Dashboard is running.")
    try:
        app.protocol("WM_DELETE_WINDOW", app.on_closing)
        app.mainloop()
    finally:
        logger.info("cStrafe UI shut down.")


if __name__ == "__main__":
    main()
