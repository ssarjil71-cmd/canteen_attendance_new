# Canteen Attendance (Flask)

Ye project Flask + MySQL based canteen/attendance management system hai.

## 1) Prerequisites

- Python 3.10+ (recommended 3.11)
- MySQL Server 8.x (ya compatible)
- `pip` package manager

## 2) Project clone/open

```bash
cd /workspace/canteen_attendance_new
```

## 3) Virtual environment banaye

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

## 4) Dependencies install kare

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## 5) `.env` banaye (important)

Project `config.py` se local `.env` automatically load karta hai. Root folder me `.env` file banakar values set kare:

```env
SECRET_KEY=super_secret_key_here
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=canteen_db
AUTO_DB_SETUP=true
```

> Notes:
> - `AUTO_DB_SETUP=true` rakhen to app startup par DB/schema auto-create/sync karne ki koshish karegi.
> - Agar MySQL credentials galat hue to app startup fail hoga.

## 6) MySQL ready kare

- MySQL service chal rahi honi chahiye.
- Jo user `.env` me diya hai uske paas database create/alter permissions honi chahiye (first run ke liye).

Optional manual schema sync:

```bash
python database/setup_database.py
```

## 7) App run kare

```bash
python app.py
```

Expected output ke baad app yahan milegi:

- http://127.0.0.1:5000

## 8) Troubleshooting

### MySQL connection error

- `.env` me `DB_HOST/DB_PORT/DB_USER/DB_PASSWORD` verify kare.
- MySQL service status check kare.

### OpenCV install issue

Agar `opencv-python` install me issue aaye to pehle wheel/build tools update kare:

```bash
pip install --upgrade pip setuptools wheel
pip install opencv-python
```

### Port already in use

Agar 5000 port busy ho to:

```bash
flask --app app run --port 5001 --debug
```

---

Agar chaho to main aapke system ke hisab se exact commands (Ubuntu/Windows/macOS) bhi de sakta hoon.
