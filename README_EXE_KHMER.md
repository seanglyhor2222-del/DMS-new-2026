# របៀបធ្វើ docsystem ជា .exe (ភាសាខ្មែរ)

## ជំហានទី ១ — ចម្លងឯកសារចូលទៅគម្រោង

ចម្លងឯកសារពីរនេះ (`run_desktop.py` និង `build_exe.bat`) ចូលទៅក្នុងថត
គម្រោងរបស់អ្នក ដាក់ជាប់នឹង `app.py` (កម្រិតដដែល មិនមែនក្នុង templates/
ឬ routes/ ទេ)។

## ជំហានទី ២ — Build

Double-click លើ `build_exe.bat` (ឬបើក terminal ក្នុងថតគម្រោង រួច
វាយ `build_exe.bat`)។ វានឹងដំឡើង PyInstaller ដោយស្វ័យប្រវត្តិ រួច
package កម្មវិធីទាំងមូល។ រង់ចាំពីរបីនាទី។

## ជំហានទី ៣ — រៀបចំមុនប្រើ

បន្ទាប់ពី build រួច នៅក្នុងថត `dist\` នឹងមាន `docsystem.exe`។
មុននឹងដំណើរការវា ត្រូវធ្វើដូចនេះ៖

1. **ចម្លង `.env`** ពី folder គម្រោង ចូលទៅដាក់ក្នុងថត `dist\` ជាប់
   នឹង `docsystem.exe` (កុំភ្លេច — បើគ្មាន .env កម្មវិធីនឹងរកមិនឃើញ
   Database password និង Gemini API key)
2. **PostgreSQL** ត្រូវដំណើរការនៅលើម៉ាស៊ីននោះជានិច្ច (exe មិនរួម
   បញ្ចូល Postgres server ទេ — វានៅតែជា server ដាច់ដោយឡែក)
3. **Tesseract OCR** (បើចង់ប្រើ fallback) ត្រូវដំឡើងដាច់ដោយឡែក
   ពី https://github.com/UB-Mannheim/tesseract/wiki ហើយកំណត់
   `TESSERACT_CMD` ក្នុង `.env` ឲ្យត្រូវ path ដំឡើងនោះ

## ជំហានទី ៤ — ដំណើរការ

Double-click លើ `docsystem.exe` ។ វានឹង៖
- ចាប់ផ្តើម server នៅ background
- បើក browser ដោយស្វ័យប្រវត្តិទៅ `http://127.0.0.1:5000`
- ទូរស័ព្ទនៅលើ Wi-Fi តែមួយនៅតែអាចភ្ជាប់សម្រាប់ស្កេន OCR បាន
  ដដែល (ព្រោះ server bind នៅ 0.0.0.0)

## បញ្ហាទូទៅ (Troubleshooting)

- **"ModuleNotFoundError" ពេលដំណើរការ .exe** — មានន័យថា library
  ណាមួយមិនត្រូវបានរួមបញ្ចូល។ បើក `build_exe.bat` រួចបន្ថែមបន្ទាត់
  `--hidden-import ឈ្មោះ_library_នោះ` រួច build ម្តងទៀត។
- **.exe បើកមិនចេញ ឬបិទភ្លាមៗ** — បើក Command Prompt រួចដំណើរការ
  `docsystem.exe` ពី command line ដើម្បីមើល error message
  (double-click នៅលើ Desktop នឹងលាក់ error window)។
- **ទំហំ .exe ធំពេក / ចាប់ផ្តើមយឺត** — `--onefile` ស្រង់ឯកសារទាំងអស់
  ទៅ temp folder រាល់ពេលចាប់ផ្តើម។ បើចង់ឲ្យលឿនជាង អាចប្តូរទៅ
  `--onedir` ជំនួស `--onefile` ក្នុង build_exe.bat (នឹងទទួលបាន folder
  មួយជំនួសឯកសារតែមួយ ប៉ុន្តែចាប់ផ្តើមលឿនជាង)។
