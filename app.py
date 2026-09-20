from datetime import datetime, date, time
from types import SimpleNamespace
import io
import os
import socket

from flask import Flask
from flask_login import LoginManager
from sqlalchemy import inspect, text

from config import Config
from extensions import db, login_manager, socketio
from models import User, FontAsset, SystemSetting


# មុខងារសម្រាប់ទាញយក Local IP Address របស់ Server ស្វ័យប្រវត្តិ
def get_server_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def upgrade_database_schema():
    columns = {column["name"] for column in inspect(db.engine).get_columns("documents")}
    additions = {
        "seq_no": "INTEGER",
        "doc_number_is_auto": "BOOLEAN DEFAULT TRUE",
        "unit": "VARCHAR(255)",
        "priority": "VARCHAR(64)",
        "status": "VARCHAR(64)",
        "remarks": "TEXT",
        "others": "TEXT",
        "created_by_id": "INTEGER",
        "updated_by_id": "INTEGER",
        "updated_at": "TIMESTAMP",
        "in_date": "DATE",
        "out_date": "DATE",
        "in_time": "TIME",
        "out_time": "TIME",
    }

    for name, definition in additions.items():
        if name not in columns:
            db.session.execute(text(f"ALTER TABLE documents ADD COLUMN {name} {definition}"))

    legacy_columns = columns | set(additions)
    if {"department_id", "unit"}.issubset(legacy_columns):
        db.session.execute(text("""
            UPDATE documents d
            SET unit = l.value_km
            FROM lookup_items l
            WHERE d.unit IS NULL AND d.department_id = l.id AND l.category = 'unit'
        """))
    if {"priority_id", "priority"}.issubset(legacy_columns):
        db.session.execute(text("""
            UPDATE documents d
            SET priority = l.value_km
            FROM lookup_items l
            WHERE d.priority IS NULL AND d.priority_id = l.id AND l.category = 'priority'
        """))
    if {"status_id", "status"}.issubset(legacy_columns):
        db.session.execute(text("""
            UPDATE documents d
            SET status = l.value_km
            FROM lookup_items l
            WHERE d.status IS NULL AND d.status_id = l.id AND l.category = 'status'
        """))
    if {"note", "remarks"}.issubset(legacy_columns):
        db.session.execute(text("UPDATE documents SET remarks = note WHERE remarks IS NULL"))
    if {"other_info", "others"}.issubset(legacy_columns):
        db.session.execute(text("UPDATE documents SET others = other_info WHERE others IS NULL"))
    if {"created_by", "created_by_id"}.issubset(legacy_columns):
        db.session.execute(text("UPDATE documents SET created_by_id = created_by WHERE created_by_id IS NULL"))
    if {"action_date", "doc_date"}.issubset(legacy_columns):
        db.session.execute(text("""
            UPDATE documents
            SET action_date = COALESCE(action_date, doc_date, CURRENT_DATE)
            WHERE action_date IS NULL
        """))
    if {"action_time", "created_at"}.issubset(legacy_columns):
        db.session.execute(text("""
            UPDATE documents
            SET action_time = COALESCE(action_time, created_at::time, CURRENT_TIME)
            WHERE action_time IS NULL
        """))

    if "in_date" not in columns:
        db.session.execute(text("UPDATE documents SET in_date = action_date WHERE in_date IS NULL AND doc_type = 'ចូល'"))
    if "out_date" not in columns:
        db.session.execute(text("UPDATE documents SET out_date = action_date WHERE out_date IS NULL AND doc_type = 'ចេញ'"))
    if "in_time" not in columns:
        db.session.execute(text("UPDATE documents SET in_time = action_time WHERE in_time IS NULL AND doc_type = 'ចូល'"))
    if "out_time" not in columns:
        db.session.execute(text("UPDATE documents SET out_time = action_time WHERE out_time IS NULL AND doc_type = 'ចេញ'"))

    db.session.execute(text("""
        UPDATE documents
        SET in_time = action_time,
            out_time = action_time
        WHERE action_time IS NOT NULL
          AND in_time IS NULL
          AND out_time IS NULL
    """))
    db.session.execute(text("""
        UPDATE documents
        SET in_date = action_date,
            out_date = action_date
        WHERE action_date IS NOT NULL
          AND in_date IS NULL
          AND out_date IS NULL
    """))
    db.session.execute(text("ALTER TABLE documents ALTER COLUMN doc_type DROP NOT NULL"))
    db.session.execute(text("ALTER TABLE documents ALTER COLUMN doc_type TYPE VARCHAR(255)"))

    db.session.execute(text("UPDATE documents SET seq_no = id WHERE seq_no IS NULL"))
    user_columns = {column["name"] for column in inspect(db.engine).get_columns("users")}
    if "last_seen_at" not in user_columns:
        db.session.execute(text("ALTER TABLE users ADD COLUMN last_seen_at TIMESTAMP"))
    db.session.commit()


def create_app():
    app = Flask(__name__)
    print("Template Folder Path:", app.template_folder)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "សូមចូលគណនីជាមុនសិន។"
    
    # ណែនាំឱ្យប្រើប្រាស់ async_mode ជា 'threading' ឬអាចប្តូរដាក់ 'eventlet' ប្រសិនបើអ្នកបាន pip install eventlet
    socketio.init_app(app, async_mode='threading')

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.context_processor
    def inject_fonts_and_network():
        try:
            all_fonts = FontAsset.query.order_by(FontAsset.created_at).all()
        except Exception:
            all_fonts = []
        default_font = next((f for f in all_fonts if f.is_default), None)
        
        ip = get_server_ip()
        port = app.config.get("PORT", 5000)
        server_url = f"http://{ip}:{port}"
        theme_colors = {
            "page_background": SystemSetting.get("page_background_color", "#0f172a"),
            "panel_background": SystemSetting.get("panel_background_color", "#1e293b"),
            "table_header": SystemSetting.get("table_header_color", "#1e293b"),
            "table_row": SystemSetting.get("table_row_color", "#172033"),
        }

        return {
            "site_fonts": all_fonts, 
            "default_font": default_font,
            "server_ip": ip,
            "server_url": server_url,
            "theme_colors": theme_colors,
        }

    from routes.auth import auth_bp
    from routes.documents import documents_bp
    from routes.admin import admin_bp
    from routes.ocr import ocr_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(ocr_bp)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["FONTS_FOLDER"], exist_ok=True)

    with app.app_context():
        db.create_all()
        upgrade_database_schema()

    return app


app = create_app()

if __name__ == "__main__":
    socketio.run(
        app, 
        host=app.config.get("HOST", "0.0.0.0"), 
        port=app.config.get("PORT", 5000), 
        debug=True, 
        allow_unsafe_werkzeug=True,
        use_reloader=False
    )