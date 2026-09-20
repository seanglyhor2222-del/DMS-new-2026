import os
import re
import io
import uuid
import tempfile
import sqlite3
import shutil
import glob
import traceback
import json
from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from extensions import db
from models import User, LookupItem, SystemSetting, AuditLog, DocumentRecord, FontAsset
from routes.auth import admin_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ---------------------------------------------------------------- Users ----
@admin_bp.route("/users")
@login_required
@admin_required
def users():
    all_users = User.query.order_by(User.created_at).all()
    online_cutoff = datetime.utcnow() - timedelta(seconds=90)
    return render_template("admin/users.html", users=all_users, online_cutoff=online_cutoff)


@admin_bp.route("/users/heartbeat", methods=["POST"])
@login_required
def user_heartbeat():
    current_user.last_seen_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"ok": True})


@admin_bp.route("/users/new", methods=["POST"])
@login_required
@admin_required
def create_user():
    f = request.form
    username = (f.get("username") or "").strip()
    if not username:
        flash("សូមបញ្ចូលឈ្មោះអ្នកប្រើ។", "danger")
        return redirect(url_for("admin.users"))

    if User.query.filter_by(username=username).first():
        flash("ឈ្មោះអ្នកប្រើនេះមានរួចហើយ។", "danger")
        return redirect(url_for("admin.users"))

    full_name = (f.get("full_name") or "").strip()
    role = f.get("role", "writer") or "writer"
    password = f.get("password") or "changeme123"

    u = User(
        username=username,
        full_name=full_name,
        role=role,
    )
    u.set_password(password)
    db.session.add(u)
    db.session.flush()
    db.session.add(AuditLog(user_id=current_user.id, action="create_user", table_name="users",
                            record_id=u.id, detail=f"Created account {u.username} ({u.role})"))
    db.session.commit()
    flash(f"បានបង្កើតគណនី {u.username} ({u.role}) ។", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/bulk-update", methods=["POST"])
@login_required
@admin_required
def bulk_update_users():
    f = request.form
    user_ids = f.getlist("user_ids")
    updated_count = 0

    for uid_str in user_ids:
        try:
            uid = int(uid_str)
        except ValueError:
            continue
        u = User.query.get(uid)
        if not u:
            continue

        changes = []

        new_username = f.get(f"username_{uid}", u.username).strip()
        if not new_username:
            flash("ឈ្មោះអ្នកប្រើមិនអាចទទេបានទេ។", "danger")
            db.session.rollback()
            return redirect(url_for("admin.users"))
        duplicate = User.query.filter(User.username == new_username, User.id != u.id).first()
        if duplicate:
            flash(f"ឈ្មោះអ្នកប្រើ {new_username} មានរួចហើយ។", "danger")
            db.session.rollback()
            return redirect(url_for("admin.users"))
        if new_username != u.username:
            changes.append(f"username: {u.username} → {new_username}")
            u.username = new_username

        new_full_name = f.get(f"full_name_{uid}", u.full_name).strip()
        if new_full_name != u.full_name:
            changes.append(f"full_name: {u.full_name} → {new_full_name}")
            u.full_name = new_full_name

        new_role = f.get(f"role_{uid}", u.role)
        if new_role != u.role:
            changes.append(f"role: {u.role} → {new_role}")
            u.role = new_role

        new_active = f"is_active_account_{uid}" in f
        if new_active != u.is_active_account:
            changes.append(f"សកម្ម: {u.is_active_account} → {new_active}")
            u.is_active_account = new_active

        new_scan = f"can_scan_ocr_{uid}" in f
        if new_scan != u.can_scan_ocr:
            changes.append(f"ស្កេនអត្ថបទ: {u.can_scan_ocr} → {new_scan}")
            u.can_scan_ocr = new_scan

        new_search = f"can_search_{uid}" in f
        if new_search != u.can_search:
            changes.append(f"ស្វែងរក: {u.can_search} → {new_search}")
            u.can_search = new_search

        new_add = f"can_add_{uid}" in f
        if new_add != u.can_add:
            changes.append(f"បញ្ចូលថ្មី: {u.can_add} → {new_add}")
            u.can_add = new_add

        new_edit = f"can_edit_{uid}" in f
        if new_edit != u.can_edit:
            changes.append(f"កែប្រែ: {u.can_edit} → {new_edit}")
            u.can_edit = new_edit

        new_password = f.get(f"new_password_{uid}", "").strip()
        if new_password:
            u.set_password(new_password)
            changes.append("បានប្តូរពាក្យសម្ងាត់")

        if changes:
            updated_count += 1
            db.session.add(AuditLog(user_id=current_user.id, action="update_user", table_name="users",
                                    record_id=u.id,
                                    detail=f"Updated {u.username}: " + "; ".join(changes)))

    db.session.commit()
    if updated_count:
        flash(f"បានរក្សាទុកការផ្លាស់ប្តូរសម្រាប់ {updated_count} គណនី។", "success")
    else:
        flash("មិនមានការផ្លាស់ប្តូរអ្វីត្រូវរក្សាទុកទេ។", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/history")
@login_required
@admin_required
def user_history(user_id):
    u = User.query.get_or_404(user_id)
    logs = AuditLog.query.filter_by(user_id=user_id).order_by(AuditLog.created_at.desc()).limit(300).all()
    return render_template("admin/history.html", target_user=u, logs=logs)


# -------------------------------------------------------------- Lookups ----
@admin_bp.route("/lookups")
@login_required
@admin_required
def lookups():
    items = {
        "doc_type": LookupItem.query.filter_by(category="doc_type").order_by(LookupItem.sort_order).all(),
        "unit": LookupItem.query.filter_by(category="unit").order_by(LookupItem.sort_order).all(),
        "priority": LookupItem.query.filter_by(category="priority").order_by(LookupItem.sort_order).all(),
        "status": LookupItem.query.filter_by(category="status").order_by(LookupItem.sort_order).all(),
    }
    settings = {
        "doc_number_mode": SystemSetting.get("doc_number_mode", "auto"),
        "doc_number_next": SystemSetting.get("doc_number_next", "1"),
        "doc_type_free_text": SystemSetting.get("doc_type_free_text", "true") == "true",
        "unit_free_text": SystemSetting.get("unit_free_text", "true") == "true",
        "priority_free_text": SystemSetting.get("priority_free_text", "true") == "true",
        "status_free_text": SystemSetting.get("status_free_text", "true") == "true",
        "freeze_table_header": SystemSetting.get("freeze_table_header") != "false",
        "page_background_color": SystemSetting.get("page_background_color", "#0f172a"),
        "panel_background_color": SystemSetting.get("panel_background_color", "#1e293b"),
        "table_header_color": SystemSetting.get("table_header_color", "#1e293b"),
        "table_row_color": SystemSetting.get("table_row_color", "#172033"),
    }
    return render_template("admin/lookups.html", items=items, settings=settings)


@admin_bp.route("/lookups/add", methods=["POST"])
@login_required
@admin_required
def add_lookup():
    f = request.form
    category = f.get("category")
    value = f.get("value_km", "").strip()
    if category in ("doc_type", "unit", "priority", "status") and value:
        item = LookupItem(category=category, value_km=value, sort_order=9999)
        db.session.add(item)
        db.session.flush()
        db.session.add(AuditLog(user_id=current_user.id, action="add_lookup", table_name="lookup_items",
                               record_id=item.id, detail=f"Added {category}: {value}"))
        db.session.commit()
        flash("បានបន្ថែមតម្លៃថ្មី។", "success")
    return redirect(url_for("admin.lookups"))


@admin_bp.route("/lookups/<int:item_id>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_lookup(item_id):
    item = LookupItem.query.get_or_404(item_id)
    item.is_active = not item.is_active
    db.session.add(AuditLog(user_id=current_user.id, action="toggle_lookup", table_name="lookup_items",
                            record_id=item.id,
                            detail=f"{'Enabled' if item.is_active else 'Disabled'} {item.category}: {item.value_km}"))
    db.session.commit()
    return redirect(url_for("admin.lookups"))


@admin_bp.route("/lookups/<int:item_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_lookup(item_id):
    item = LookupItem.query.get_or_404(item_id)
    db.session.add(AuditLog(user_id=current_user.id, action="delete_lookup", table_name="lookup_items",
                            record_id=item.id, detail=f"Deleted {item.category}: {item.value_km}"))
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for("admin.lookups"))


@admin_bp.route("/settings", methods=["POST"])
@login_required
@admin_required
def update_settings():
    f = request.form
    doc_number_mode = (f.get("doc_number_mode") or "").strip()
    if doc_number_mode not in ("auto", "manual"):
        flash("សូមเลือกរបៀបផ្តល់លេខលិខិតមុន។", "danger")
        return redirect(url_for("admin.lookups"))

    doc_number_next_raw = (f.get("doc_number_next") or "").strip()
    if not doc_number_next_raw:
        flash("លេខបន្ទាប់ (Auto counter) មិនអាចទទេបានទេ។", "danger")
        return redirect(url_for("admin.lookups"))
    try:
        doc_number_next = int(doc_number_next_raw)
        if doc_number_next < 1:
            raise ValueError
    except ValueError:
        flash("លេខបន្ទាប់ (Auto counter) ត្រូវតែជាលេខវិជ្ជមានដែលមិនតូចជាង 1 ។", "danger")
        return redirect(url_for("admin.lookups"))

    SystemSetting.set("doc_number_mode", doc_number_mode)
    SystemSetting.set("doc_number_next", str(doc_number_next))
    SystemSetting.set("doc_type_free_text", "true" if "doc_type_free_text" in f else "false")
    SystemSetting.set("unit_free_text", "true" if "unit_free_text" in f else "false")
    SystemSetting.set("priority_free_text", "true" if "priority_free_text" in f else "false")
    SystemSetting.set("status_free_text", "true" if "status_free_text" in f else "false")
    SystemSetting.set("freeze_table_header", "true" if f.get("freeze_table_header") in ("true", "on") else "false")
    color_defaults = {
        "page_background_color": "#0f172a",
        "panel_background_color": "#1e293b",
        "table_header_color": "#1e293b",
        "table_row_color": "#172033",
    }
    for key, default in color_defaults.items():
        value = (f.get(key) or default).strip()
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            value = default
        SystemSetting.set(key, value)
    db.session.add(AuditLog(user_id=current_user.id, action="update_settings", table_name="system_settings",
                            detail=f"doc_number_mode={doc_number_mode}, "
                                   f"doc_type_free_text={'doc_type_free_text' in f}, "
                                   f"unit_free_text={'unit_free_text' in f}, "
                                   f"priority_free_text={'priority_free_text' in f}, "
                                   f"status_free_text={'status_free_text' in f}, "
                                   f"freeze_table_header={'freeze_table_header' in f}"))
    db.session.commit()
    flash("បានធ្វើបច្ចុប្បន្នភាពការកំណត់។", "success")
    return redirect(url_for("admin.lookups"))


@admin_bp.route("/reports/document/<int:record_id>/audit")
@login_required
@admin_required
def document_audit(record_id):
    logs = AuditLog.query.filter(
        AuditLog.record_id == record_id,
        AuditLog.action.in_(["create", "edit", "delete"]),
    ).order_by(AuditLog.created_at.asc(), AuditLog.id.asc()).all()
    versions = []
    for log in logs:
        try:
            payload = json.loads(log.detail or "")
        except (TypeError, ValueError):
            continue
        if payload.get("format") != "document_snapshot_v1":
            continue
        versions.append({
            "action": payload.get("action", log.action),
            "before": payload.get("before"),
            "after": payload.get("after"),
            "username": log.user.username if log.user else "-",
            "full_name": log.user.full_name if log.user else "-",
            "role": log.user.role if log.user else "-",
            "created_at": log.created_at.strftime("%d-%m-%Y %H:%M:%S") if log.created_at else "-",
        })
    return render_template("admin/document_audit.html", record_id=record_id, versions=versions)


# --------------------------------------------------------------- Reports ----
@admin_bp.route("/reports")
@login_required
@admin_required
def reports():
    filters = {"search": request.args.get("search", "").strip()}
    sort_by = request.args.get("sort_by", "seq_no")
    sort_dir = request.args.get("sort_dir", "asc")

    query = DocumentRecord.query.outerjoin(User, DocumentRecord.created_by_id == User.id)

    if filters["search"]:
        search_term = f"%{filters['search']}%"
        query = query.filter(db.or_(
            DocumentRecord.doc_number.ilike(search_term),
            DocumentRecord.subject.ilike(search_term),
            DocumentRecord.unit.ilike(search_term),
        ))

    sortable_columns = {
        "seq_no": DocumentRecord.seq_no,
        "doc_number": DocumentRecord.doc_number,
        "doc_date": DocumentRecord.doc_date,
        "subject": DocumentRecord.subject,
        "doc_type": DocumentRecord.doc_type,
        "unit": DocumentRecord.unit,
        "quantity": DocumentRecord.quantity,
        "action_date": DocumentRecord.action_date,
        "action_time": DocumentRecord.action_time,
        "priority": DocumentRecord.priority,
        "status": DocumentRecord.status,
        "created_by": User.username,
    }
    sort_column = sortable_columns.get(sort_by, DocumentRecord.action_date)
    if sort_dir not in ("asc", "desc"):
        sort_dir = "desc"
    query = query.order_by(sort_column.asc() if sort_dir == "asc" else sort_column.desc())

    records = query.all()
    document_audits = {}
    for record in records:
        entries = []
        logs = AuditLog.query.filter(
            AuditLog.record_id == record.id,
            AuditLog.action.in_(["create", "edit"]),
        ).order_by(AuditLog.created_at.asc(), AuditLog.id.asc()).all()
        for log in logs:
            try:
                payload = json.loads(log.detail or "")
            except (TypeError, ValueError):
                continue
            if payload.get("format") != "document_snapshot_v1":
                continue
            entries.append({
                "action": payload.get("action", log.action),
                "before": payload.get("before"),
                "after": payload.get("after"),
                "created_at": log.created_at.strftime("%d-%m-%Y %H:%M") if log.created_at else "-",
                "user": (log.user.full_name or log.user.username) if log.user else "-",
            })
        document_audits[record.id] = entries
    sort_links = {}
    for column_name in sortable_columns:
        link_args = filters.copy()
        link_args["sort_by"] = column_name
        link_args["sort_dir"] = "asc" if sort_by == column_name and sort_dir == "desc" else "desc"
        sort_links[column_name] = url_for("admin.reports", **link_args)
    return render_template("admin/reports.html", records=records,
                           filters=filters, sort_by=sort_by, sort_dir=sort_dir,
                           sort_links=sort_links, document_audits=document_audits)


# ------------------------------------------------------------ Backup & Restore ----
@admin_bp.route("/system/backup-page", methods=["GET"])
@login_required
@admin_required
def backup_page():
    return render_template("admin/backup.html")


@admin_bp.route("/system/backup", methods=["GET"])
@login_required
@admin_required
def backup_database():
    temp_path = None
    try:
        fd, temp_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)

        data = {
            "users": [{"id": u.id, "username": u.username, "role": u.role, "full_name": u.full_name, "password_hash": u.password_hash} for u in User.query.all()],
            "lookups": [{"id": l.id, "category": l.category, "value_km": l.value_km, "sort_order": l.sort_order, "is_active": l.is_active} for l in LookupItem.query.all()],
            "fonts": [{"id": f.id, "family_name": f.family_name, "original_filename": f.original_filename, "stored_filename": f.stored_filename, "is_default": f.is_default} for f in FontAsset.query.all()],
            "documents": [{
                "id": d.id, "seq_no": d.seq_no, "doc_type": d.doc_type, "doc_number": d.doc_number,
                "doc_date": d.doc_date.isoformat() if d.doc_date else None,
                "subject": d.subject, "unit": d.unit, "quantity": d.quantity, "priority": d.priority,
                "action_date": d.action_date.isoformat() if d.action_date else None,
                "action_time": d.action_time.strftime("%H:%M") if d.action_time else None,
                "status": d.status, "remarks": d.remarks, "others": d.others
            } for d in DocumentRecord.query.all()]
        }

        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        db.session.add(AuditLog(user_id=current_user.id, action="backup_database", table_name="system",
                                record_id=0, detail="Downloaded complete system database backup as JSON"))
        db.session.commit()

        return send_file(
            temp_path,
            as_attachment=True,
            download_name="document_system_backup.json",
            mimetype="application/json",
        )

    except Exception as e:
        traceback.print_exc()
        flash(f"មានបញ្ហាក្នុងការ Backup: {str(e)}", "danger")
        return redirect(url_for("admin.backup_page"))
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass


@admin_bp.route("/system/restore", methods=["POST"])
@login_required
@admin_required
def restore_database():
    if "backup_file" not in request.files:
        flash("មិនមានឯកសារត្រូវបានជ្រើសរើសទេ!", "danger")
        return redirect(url_for("admin.backup_page"))

    file = request.files["backup_file"]
    if file.filename == "":
        flash("សូមជ្រើសរើសឯកសារ Database", "danger")
        return redirect(url_for("admin.backup_page"))

    if file:
        try:
            if not file.filename.lower().endswith(".json"):
                flash("សូមជ្រើសរើសឯកសារប្រើទ្រង់ទ្រាយ JSON เท่านั้น។", "danger")
                return redirect(url_for("admin.backup_page"))

            content = file.read().decode("utf-8")
            data = json.loads(content)

            if "users" in data:
                for u_data in data["users"]:
                    existing = User.query.get(u_data["id"])
                    if not existing:
                        new_user = User(
                            id=u_data["id"],
                            username=u_data["username"],
                            role=u_data["role"],
                            full_name=u_data.get("full_name", ""),
                            password_hash=u_data.get("password_hash", "")
                        )
                        db.session.add(new_user)

            if "lookups" in data:
                for l_data in data["lookups"]:
                    existing = LookupItem.query.get(l_data["id"])
                    if not existing:
                        new_lookup = LookupItem(
                            id=l_data["id"],
                            category=l_data["category"],
                            value_km=l_data["value_km"],
                            sort_order=l_data.get("sort_order", 99),
                            is_active=l_data.get("is_active", True)
                        )
                        db.session.add(new_lookup)

            if "fonts" in data:
                for f_data in data["fonts"]:
                    existing = FontAsset.query.get(f_data["id"])
                    if not existing:
                        new_font = FontAsset(
                            id=f_data["id"],
                            family_name=f_data["family_name"],
                            original_filename=f_data["original_filename"],
                            stored_filename=f_data.get("stored_filename", ""),
                            is_default=f_data.get("is_default", False)
                        )
                        db.session.add(new_font)

            if "documents" in data:
                from datetime import datetime
                for d_data in data["documents"]:
                    existing = DocumentRecord.query.get(d_data["id"])
                    if not existing:
                        doc_date = datetime.strptime(d_data["doc_date"], "%Y-%m-%d").date() if d_data.get("doc_date") else None
                        action_date = datetime.strptime(d_data["action_date"], "%Y-%m-%d").date() if d_data.get("action_date") else None
                        action_time = datetime.strptime(d_data["action_time"], "%H:%M").time() if d_data.get("action_time") else None

                        new_doc = DocumentRecord(
                            id=d_data["id"],
                            seq_no=d_data.get("seq_no", 1),
                            doc_type=d_data.get("doc_type", "in"),
                            doc_number=d_data.get("doc_number", ""),
                            doc_date=doc_date,
                            subject=d_data.get("subject", ""),
                            unit=d_data.get("unit", ""),
                            quantity=d_data.get("quantity"),
                            priority=d_data.get("priority", ""),
                            action_date=action_date,
                            action_time=action_time,
                            status=d_data.get("status", ""),
                            remarks=d_data.get("remarks", ""),
                            others=d_data.get("others", "")
                        )
                        db.session.add(new_doc)

            db.session.add(AuditLog(
                user_id=current_user.id,
                action="restore_database",
                table_name="system",
                record_id=0,
                detail="Restored complete system database including documents from JSON backup"
            ))
            db.session.commit()
            flash("បាន Restore ទិន្នន័យចូលប្រព័ន្ធដោយជោគជ័យ! សូម Refresh ឡើងវិញ។", "success")

        except Exception as e:
            db.session.rollback()
            traceback.print_exc()
            flash(f"មានបញ្ហាក្នុងការ Restore (ទម្រង់ဖាយមិនត្រឹមត្រូវ): {str(e)}", "danger")

    return redirect(url_for("admin.backup_page"))


# ------------------------------------------------------------ All history --
@admin_bp.route("/history")
@login_required
@admin_required
def all_history():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(500).all()
    return render_template("admin/history.html", target_user=None, logs=logs)


# ---------------------------------------------------------------- Fonts ----
@admin_bp.route("/fonts")
@login_required
@admin_required
def fonts():
    all_fonts = FontAsset.query.order_by(FontAsset.created_at).all()
    return render_template("admin/fonts.html", fonts=all_fonts)


@admin_bp.route("/fonts/upload", methods=["POST"])
@login_required
@admin_required
def upload_font():
    file = request.files.get("font_file")
    display_name = request.form.get("display_name", "").strip()

    if not file or file.filename == "":
        flash("សូមជ្រើសរើសឯកសារពុម្ពអក្សរ។", "danger")
        return redirect(url_for("admin.fonts"))

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in current_app.config["ALLOWED_FONT_EXTENSIONS"]:
        flash("ប្រភេទឯកសារមិនត្រូវបានអនុញ្ញាតទេ (.ttf .otf .woff .woff2 តែប៉ុណ្ណោះ)។", "danger")
        return redirect(url_for("admin.fonts"))

    if not display_name:
        display_name = os.path.splitext(secure_filename(file.filename))[0]

    family_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", display_name).strip("_") or f"font_{uuid.uuid4().hex[:6]}"
    base_family, n = family_name, 1
    while FontAsset.query.filter_by(family_name=family_name).first():
        n += 1
        family_name = f"{base_family}_{n}"

    fonts_dir = current_app.config["FONTS_FOLDER"]
    os.makedirs(fonts_dir, exist_ok=True)
    stored_filename = f"{uuid.uuid4().hex[:10]}.{ext}"
    file.save(os.path.join(fonts_dir, stored_filename))

    fa = FontAsset(
        original_filename=secure_filename(file.filename),
        stored_filename=stored_filename,
        family_name=family_name,
        uploaded_by_id=current_user.id,
    )
    db.session.add(fa)
    db.session.flush()
    db.session.add(AuditLog(user_id=current_user.id, action="upload_font", table_name="font_assets",
                            record_id=fa.id, detail=f"Uploaded font {fa.original_filename} ({fa.family_name})"))
    db.session.commit()
    flash(f"បានបន្ថែមពុម្ពអក្សរ {fa.original_filename} ។ ឥឡូវប្រព័ន្ធអាចប្រើវាបានហើយ។", "success")
    return redirect(url_for("admin.fonts"))


@admin_bp.route("/fonts/<int:font_id>/set-default", methods=["POST"])
@login_required
@admin_required
def set_default_font(font_id):
    target = FontAsset.query.get_or_404(font_id)
    FontAsset.query.update({FontAsset.is_default: False})
    target.is_default = True
    db.session.add(AuditLog(user_id=current_user.id, action="set_default_font", table_name="font_assets",
                            record_id=target.id, detail=f"Set default font: {target.family_name}"))
    db.session.commit()
    flash(f"បានកំណត់ {target.original_filename} ជាពុម្ពអក្សរលំនាំដើមរបស់ប្រព័ន្ធ។", "success")
    return redirect(url_for("admin.fonts"))


@admin_bp.route("/fonts/<int:font_id>/unset-default", methods=["POST"])
@login_required
@admin_required
def unset_default_font(font_id):
    target = FontAsset.query.get_or_404(font_id)
    target.is_default = False
    db.session.add(AuditLog(user_id=current_user.id, action="unset_default_font", table_name="font_assets",
                            record_id=target.id, detail=f"Unset default font: {target.family_name}"))
    db.session.commit()
    flash("បានត្រឡប់ទៅពុម្ពអក្សរធម្មតាវិញ។", "success")
    return redirect(url_for("admin.fonts"))


@admin_bp.route("/fonts/<int:font_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_font(font_id):
    fa = FontAsset.query.get_or_404(font_id)
    fonts_dir = current_app.config["FONTS_FOLDER"]
    path = os.path.join(fonts_dir, fa.stored_filename)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
    db.session.add(AuditLog(user_id=current_user.id, action="delete_font", table_name="font_assets",
                            record_id=fa.id, detail=f"Deleted font {fa.original_filename}"))
    db.session.delete(fa)
    db.session.commit()
    flash("បានលុបពុម្ពអក្សរ។", "success")
    return redirect(url_for("admin.fonts"))