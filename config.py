import os
import sys
from dotenv import load_dotenv

load_dotenv()

# រកមើលថា កំពុងរត់ជា .exe (packaged ដោយ PyInstaller) ឬជា python script ធម្មតា
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)      # folder ដែល docsystem.exe នៅ
else:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-in-production")

    # ---- PostgreSQL (local) ----
    DB_USER = os.environ.get("DB_USER", "docsystem_user")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "docsystem_pass")
    DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
    DB_PORT = os.environ.get("DB_PORT", "5432")
    DB_NAME = os.environ.get("DB_NAME", "docsystem")

    # បន្ថែមជម្រើសទាំងនេះដើម្បីការពារការដាច់ការតភ្ជាប់ជាមួយ PostgreSQL
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ---- Uploads (OCR capture images) ----
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    MAX_CONTENT_LENGTH = 12 * 1024 * 1024  # 12 MB per image

    # ---- Fonts (admin-managed Khmer/other font files, used for @font-face) ----
    FONTS_FOLDER = os.path.join(BASE_DIR, "static", "fonts")
    ALLOWED_FONT_EXTENSIONS = {"ttf", "otf", "woff", "woff2"}

    # ---- Tesseract ----
    # លំនាំដើម ប្រើ tesseract portable folder ដែលនៅជាប់ docsystem.exe
    # (កំណត់ TESSERACT_CMD ក្នុង .env បើចង់ប្រើ Tesseract ដែលដំឡើងលើប្រព័ន្ធវិញ)
    TESSERACT_CMD = os.environ.get(
        "TESSERACT_CMD",
        os.path.join(BASE_DIR, "tesseract", "tesseract.exe")
    )
    OCR_LANGUAGES = "khm+eng"

    # ---- Gemini (used to clean up OCR text) ----
    # Set GEMINI_API_KEY in your .env file — never hardcode API keys in source.
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

    # ---- Server ----
    # 0.0.0.0 so the phone on the same Wi-Fi/LAN can reach the PC
    HOST = os.environ.get("HOST", "0.0.0.0")
    PORT = int(os.environ.get("PORT", 5000))