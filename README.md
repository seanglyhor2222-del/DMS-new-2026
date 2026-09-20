# ប្រព័ន្ធគ្រប់គ្រងលិខិត ចេញ/ចូល (Doc In/Out Register)

Flask + PostgreSQL + Flask-SocketIO system with:

- Full Doc In/Out table (all the columns from your spec, Khmer labels kept as-is)
- Role-based accounts: **Admin** and **Writer**, with per-user feature toggles
  (edit, search, OCR-scan, active/disabled) that only Admin can change
- Search bar above the table: text search + date range + In/Out filter + sort by any column
  (including sort by ចេញ/ចូល)
- Admin panel: manage users, manage dropdown lists (អង្គភាព / អាទិភាព / ស្ថានភាព),
  toggle whether each list allows free typing, control លេខលិខិត auto/manual mode, view audit history
- **Phone camera → PC auto-fill OCR**: scan a QR code on the PC screen with your phone,
  take a photo, and the extracted Khmer+English text is pushed instantly (WebSocket) into the
  "កម្មវត្ថុ" field on the PC — no app install needed on the phone, just a browser.

---

## 1. Prerequisites

Install these on the PC that will run the server:

1. **Python 3.10+**
2. **PostgreSQL** (local) — https://www.postgresql.org/download/
3. **Tesseract OCR** with Khmer language data:
   - **Windows**: install from https://github.com/UB-Mannheim/tesseract/wiki (the installer
     includes a language picker — tick "Khmer"). Note the install path, e.g.
     `C:\Program Files\Tesseract-OCR\tesseract.exe`.
   - **Ubuntu/Debian**: `sudo apt install tesseract-ocr tesseract-ocr-khm`
   - **macOS**: `brew install tesseract tesseract-lang`
   - Verify: `tesseract --list-langs` should list `khm` and `eng`.

---

## 2. Setup

```bash
cd docsystem
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

Create the PostgreSQL database and user:

```sql
-- run inside psql
CREATE USER docsystem_user WITH PASSWORD 'docsystem_pass';
CREATE DATABASE docsystem OWNER docsystem_user;
```

Copy the env template and edit as needed:

```bash
cp .env.example .env
```

Edit `.env` — especially `TESSERACT_CMD` on Windows, and your DB credentials.

Create tables and a first admin/writer account:

```bash
python seed.py
```

This prints the default logins:
- `admin / admin123` (change the password after first login, via Admin → Users)
- `writer1 / writer123`

---

## 3. Run

```bash
python app.py
```

The server starts on `http://0.0.0.0:5000`.

**Important — access it via your PC's LAN IP, not `localhost`**, so the QR code
generated for OCR scanning is reachable from your phone:

- Find your PC's local IP: `ipconfig` (Windows) / `ifconfig` or `ip a` (Mac/Linux) —
  look for something like `192.168.1.23`.
- On the PC browser open: `http://192.168.1.23:5000`
- Make sure your **phone is on the same Wi-Fi network** as the PC.
- Make sure your OS firewall allows inbound connections on port 5000.

---

## 4. Using the OCR camera-to-PC feature

1. On the PC, open **+ បញ្ចូលថ្មី** (new document) or edit a document.
2. Click **📷 ស្កេនតាមទូរស័ព្ទ** next to "កម្មវត្ថុ".
3. A QR code pops up. Scan it with your phone's camera (or just open the printed URL).
4. On the phone page, tap **📸 បើកកាមេរ៉ា**, take the photo, then **⬆️ ផ្ញើទៅកុំព្យូទ័រ**.
5. The server runs Tesseract (`khm+eng`), cleans the text, and pushes it to the PC's
   "កម្មវត្ថុ" field over WebSocket — it appears within a second or two, no page refresh needed.
6. The pairing code expires after 15 minutes and can only be used from that one document form.

How it works technically:
- PC page requests a short-lived pairing code (`/api/ocr/session/new`) and joins a
  Socket.IO room named after that code.
- The QR code just encodes the mobile page URL `/mobile/<code>`.
- The phone uploads the photo to `/api/ocr/upload/<code>` (plain HTTP POST, no login needed —
  the code itself is the access control and is short-lived).
- The server runs OCR, then does `socketio.emit("ocr_result", ..., room=code)`, which the
  PC page receives instantly and writes into the input field.

---

## 5. Roles & permissions

- **Admin**: full access to everything, always — regardless of any checkbox.
- **Writer**: normal data-entry account. Admin controls, per writer, from **Admin → Users**:
  - **សកម្ម (Active)** — turn the account on/off
  - **ស្កេនអត្ថបទ (can_scan_ocr)** — allow/deny the phone-camera OCR feature
  - **ស្វែងរក (can_search)** — allow/deny using the search bar
  - **កែប្រែ (can_edit)** — allow/deny editing existing records
  - Admin can also view each user's action **history** (create/edit/delete/OCR scans/logins).

Only Admin can change:
- **ល.រ** (record sequence number) on an existing record
- Whether **លេខលិខិត** is system-wide Auto or Manual (Admin → ការកំណត់ / បញ្ជី)
- The dropdown lists for អង្គភាព / អាទិភាពលិខិត / ស្ថានភាព, and whether each of those
  fields also allows free typing in addition to the dropdown

---

## 6. Project structure

```
docsystem/
  app.py                 # Flask app factory + SocketIO run
  config.py               # env-based configuration
  extensions.py            # db, login_manager, socketio singletons
  models.py                # User, DocumentRecord, LookupItem, SystemSetting, AuditLog
  seed.py                  # creates first admin/writer + default dropdown values
  routes/
    auth.py                # login/logout + permission decorators
    documents.py            # dashboard (search/filter/sort) + CRUD
    admin.py                # user mgmt, dropdown mgmt, settings, history
    ocr.py                  # QR pairing, mobile capture upload, Tesseract OCR, SocketIO push
  templates/                # Jinja2 + Tailwind (CDN) + Khmer font
  static/
    js/main.js              # QR modal + Socket.IO listener (desktop side)
    css/style.css
```

---

## 7. Notes / things you may want to adjust

- The QR image is generated via a free public QR API (`api.qrserver.com`) called from the
  PC browser — that needs the PC to have normal internet access (only for the QR image itself,
  the OCR upload stays fully on your local network). If you'd rather generate QR codes
  fully offline, swap that `<img>` src in `static/js/main.js` for a client-side JS QR library.
- Uploaded phone photos are saved to `static/uploads/` for the OCR pass; you can add a
  cleanup cron/task if you want to purge them periodically.
- For production use: put this behind a real WSGI/ASGI server setup (e.g. `eventlet` is
  already wired in via Flask-SocketIO), set a strong `SECRET_KEY`, and change the default
  seeded passwords immediately.
