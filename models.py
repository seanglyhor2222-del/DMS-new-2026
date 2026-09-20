from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(128), nullable=False, default="")
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(16), nullable=False, default="writer")

    is_active_account = db.Column(db.Boolean, default=True, nullable=False)
    can_scan_ocr = db.Column(db.Boolean, default=True, nullable=False)
    can_search = db.Column(db.Boolean, default=True, nullable=False)
    can_add = db.Column(db.Boolean, default=True, nullable=False)
    can_edit = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime, nullable=True)
    last_seen_at = db.Column(db.DateTime, nullable=True)

    documents = db.relationship("DocumentRecord", backref="creator",
                                foreign_keys="DocumentRecord.created_by_id")
    logs = db.relationship("AuditLog", backref="user", lazy="dynamic")

    @property
    def is_active(self):
        return self.is_active_account

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    def is_admin(self):
        return self.role == "admin"

    def permission(self, name):
        if self.is_admin():
            return True
        if name == "can_search":
            return True
        return bool(getattr(self, name, False))

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "full_name": self.full_name,
            "role": self.role,
            "is_active_account": self.is_active_account,
            "can_scan_ocr": self.can_scan_ocr,
            "can_search": self.can_search,
            "can_add": self.can_add,
            "can_edit": self.can_edit,
            "last_login_at": self.last_login_at.strftime("%Y-%m-%d %H:%M") if self.last_login_at else None,
        }


class LookupItem(db.Model):
    __tablename__ = "lookup_items"

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(32), nullable=False, index=True)
    value_km = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {"id": self.id, "category": self.category, "value_km": self.value_km,
                "is_active": self.is_active}


class SystemSetting(db.Model):
    __tablename__ = "system_settings"

    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.String(255), nullable=False)

    @staticmethod
    def get(key, default=None):
        row = SystemSetting.query.get(key)
        return row.value if row else default

    @staticmethod
    def set(key, value):
        row = SystemSetting.query.get(key)
        if row:
            row.value = str(value)
        else:
            row = SystemSetting(key=key, value=str(value))
            db.session.add(row)
        return row


class DocumentRecord(db.Model):
    # ✅ ប្រើឈ្មោះ Table ក្នុង Database គឺ "documents" ត្រឹមត្រូវតាម pgAdmin របស់អ្នក
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    seq_no = db.Column(db.Integer, nullable=False)
    doc_type = db.Column(db.String(255), nullable=True)
    doc_number = db.Column(db.String(64), nullable=True)
    doc_number_is_auto = db.Column(db.Boolean, default=True)
    doc_date = db.Column(db.Date, default=date.today)
    subject = db.Column(db.Text, nullable=True)
    unit = db.Column(db.String(255), nullable=True)
    quantity = db.Column(db.Integer, nullable=True)
    priority = db.Column(db.String(64), nullable=True)

    # ✅ ប្រើ action_date និង action_time ឱ្យត្រូវបេះបិទជាមួយ Database
    action_date = db.Column(db.Date, nullable=True)
    action_time = db.Column(db.Time, nullable=True)
    in_date = db.Column(db.Date, nullable=True)
    out_date = db.Column(db.Date, nullable=True)
    in_time = db.Column(db.Time, nullable=True)
    out_time = db.Column(db.Time, nullable=True)

    status = db.Column(db.String(64), nullable=True)
    remarks = db.Column(db.Text, nullable=True)
    others = db.Column(db.Text, nullable=True)

    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "seq_no": self.seq_no,
            "doc_type": self.doc_type,
            "doc_number": self.doc_number,
            "doc_date": self.doc_date.isoformat() if self.doc_date else None,
            "subject": self.subject,
            "unit": self.unit,
            "quantity": self.quantity,
            "priority": self.priority,
            "action_date": self.action_date.isoformat() if self.action_date else None,
            "action_time": self.action_time.strftime("%H:%M") if self.action_time else None,
            "in_date": self.in_date.isoformat() if self.in_date else None,
            "out_date": self.out_date.isoformat() if self.out_date else None,
            "in_time": self.in_time.strftime("%H:%M") if self.in_time else None,
            "out_time": self.out_time.strftime("%H:%M") if self.out_time else None,
            "status": self.status,
            "remarks": self.remarks,
            "others": self.others,
            "created_by": self.creator.full_name if self.creator else None,
        }


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(64), nullable=False)
    table_name = db.Column(db.String(64), default="documents")
    record_id = db.Column(db.Integer, nullable=True)
    detail = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class FontAsset(db.Model):
    __tablename__ = "font_assets"

    id = db.Column(db.Integer, primary_key=True)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False, unique=True)
    family_name = db.Column(db.String(128), nullable=False, unique=True)
    is_default = db.Column(db.Boolean, default=False, nullable=False)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "original_filename": self.original_filename,
            "family_name": self.family_name,
            "is_default": self.is_default,
        }