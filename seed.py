"""
Run once after the database exists:
    python seed.py
Creates the first admin account and a few default dropdown values.
"""
from app import create_app
from extensions import db
from models import User, LookupItem, SystemSetting

app = create_app()

with app.app_context():
    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", full_name="System Administrator", role="admin")
        admin.set_password("admin123")  # CHANGE THIS after first login
        db.session.add(admin)
        print("Created admin user -> username: admin / password: admin123 (change it!)")

    if not User.query.filter_by(username="writer1").first():
        writer = User(username="writer1", full_name="Sample Writer", role="writer")
        writer.set_password("writer123")
        db.session.add(writer)
        print("Created writer user -> username: writer1 / password: writer123")

    defaults = {
        "doc_type": ["ចូល", "ចេញ"],
        "unit": ["នាយកដ្ឋានរដ្ឋបាល", "នាយកដ្ឋានហិរញ្ញវត្ថុ", "នាយកដ្ឋានផែនការ"],
        "priority": ["បន្ទាន់", "ធម្មតា", "សំខាន់ណាស់"],
        "status": ["កំពុងដំណើរការ", "រួចរាល់", "រង់ចាំពិនិត្យ"],
    }
    for category, values in defaults.items():
        for i, v in enumerate(values):
            exists = LookupItem.query.filter_by(category=category, value_km=v).first()
            if not exists:
                db.session.add(LookupItem(category=category, value_km=v, sort_order=i))

    if not SystemSetting.query.get("doc_number_mode"):
        db.session.add(SystemSetting(key="doc_number_mode", value="auto"))
    if not SystemSetting.query.get("doc_number_next"):
        db.session.add(SystemSetting(key="doc_number_next", value="1"))
    if not SystemSetting.query.get("unit_free_text"):
        db.session.add(SystemSetting(key="unit_free_text", value="true"))
    if not SystemSetting.query.get("priority_free_text"):
        db.session.add(SystemSetting(key="priority_free_text", value="true"))
    if not SystemSetting.query.get("status_free_text"):
        db.session.add(SystemSetting(key="status_free_text", value="true"))

    db.session.commit()
    print("Seed complete.")
