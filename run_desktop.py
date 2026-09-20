"""
ចំណុចចូល (entry point) សម្រាប់ package ជា .exe ដោយ PyInstaller។
កុំប្រើ app.py ដោយផ្ទាល់ — ចូរប្រើឯកសារនេះជំនួសវិញ ព្រោះ:
  1. app.py ប្រើ debug=True ដែលមិនដំណើរការត្រឹមត្រូវក្នុង .exe
     (Flask debug mode បង្កើត subprocess ថ្មីឡើងវិញ ដែលធ្វើឲ្យ
      .exe គាំង ឬបើកទ្វេដង)
  2. ឯកសារនេះនឹងបើក browser ដោយស្វ័យប្រវត្តិឲ្យ ដូចជាកម្មវិធីលើ
     desktop ធម្មតា
  3. ឯកសារនេះនឹងអាន .env ពីទីតាំងជាប់នឹង .exe ខ្លួនឯង មិនមែនពី
     ក្នុងឯកសារបណ្តោះអាសន្នដែល PyInstaller ស្រង់ចេញនោះទេ — ដូច្នេះ
     អ្នកអាចកែ API key / database password ដោយមិនចាំបាច់ build
     ឡើងវិញ
"""
import os
import sys
import threading
import webbrowser

if getattr(sys, "frozen", False):
    # PyInstaller onefile: ឯកសារដែលបានបញ្ចូល (templates/, static/)
    # ត្រូវបានស្រង់ចេញទៅថតបណ្តោះអាសន្ន sys._MEIPASS ពេលចាប់ផ្តើម —
    # កម្មវិធីត្រូវរកមើលឯកសារទាំងនោះនៅទីនោះ
    BUNDLE_DIR = sys._MEIPASS

    # ប៉ុន្តែ .env ត្រូវអានពីទីតាំងជាប់នឹង .exe ខ្លួនឯង (មិនមែនថត
    # បណ្តោះអាសន្ន) ដើម្បីឲ្យអ្នកកែប្រែបានដោយមិនចាំបាច់ build ឡើងវិញ
    from dotenv import load_dotenv
    EXE_DIR = os.path.dirname(sys.executable)
    load_dotenv(os.path.join(EXE_DIR, ".env"))

    os.chdir(BUNDLE_DIR)

# នាំចូល app បន្ទាប់ពី path បានរៀបចំរួច (កំណត់ចេតនាឲ្យនាំចូលនៅទីនេះ)
from app import app, socketio  # noqa: E402


def _open_browser():
    port = app.config.get("PORT", 5000)
    webbrowser.open(f"http://127.0.0.1:{port}")


if __name__ == "__main__":
    # រង់ចាំ ១.៥ វិនាទីឲ្យ server ចាប់ផ្តើមរួច សិន មុននឹងបើក browser
    threading.Timer(1.5, _open_browser).start()

    # host នៅតែ 0.0.0.0 ដើម្បីឲ្យទូរស័ព្ទលើបណ្តាញ Wi-Fi តែមួយអាច
    # ភ្ជាប់មកលក្ខណៈស្កេន OCR បាន — មានតែ tab ដែលបើកស្វ័យប្រវត្តិប៉ុណ្ណោះ
    # ដែលប្រើ 127.0.0.1
    socketio.run(
        app,
        host=app.config.get("HOST", "0.0.0.0"),
        port=app.config.get("PORT", 5000),
        debug=False,
        allow_unsafe_werkzeug=True,
        use_reloader=False,
    )
