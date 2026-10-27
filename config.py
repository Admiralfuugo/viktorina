import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ["BOT_TOKEN"]
# Boshlang'ich adminlar va kanal — keyin paneldan boshqariladi
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}
CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip() or None
NOTIFY_ADMINS = os.getenv("NOTIFY_ADMINS", "1") == "1"
DB_PATH = os.getenv("DB_PATH", "viktorina.db")

PANEL_HOST = os.getenv("PANEL_HOST", "127.0.0.1")
PANEL_PORT = int(os.getenv("PANEL_PORT", "8000"))
PANEL_USER = os.getenv("PANEL_USER", "admin")
PANEL_PASSWORD = os.getenv("PANEL_PASSWORD", "")
SECRET_KEY = os.getenv("SECRET_KEY", BOT_TOKEN)
