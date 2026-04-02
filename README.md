# 📂 DocShare

No-login document sharing platform for PDFs and PowerPoints.
Built with **Python + Flask** and **Supabase** (database + storage).

---

## 🚀 Run Locally

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the SQL setup in your Supabase SQL Editor (supabase_setup.sql)

# 3. Start the app
python app.py

# Visit http://localhost:5000
```

---

## 🌐 Deploy to Render (Free)

1. Push this folder to a GitHub repo
2. Go to render.com → New → Web Service → connect repo
3. Add environment variables in the Render dashboard:
   - SUPABASE_URL = https://zulmksqpkolxqqrzmvdh.supabase.co
   - SUPABASE_KEY = your_key_here
4. Build command:  pip install -r requirements.txt
5. Start command:  gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
6. Click Deploy → live in ~2 min at yourapp.onrender.com

---

## 📁 Project Structure

```
docshare/
├── app.py                  ← Flask backend (all routes + Supabase calls)
├── requirements.txt        ← flask, requests, gunicorn
├── Procfile                ← for Render/Railway deployment
├── runtime.txt             ← Python 3.12
├── supabase_setup.sql      ← run once in Supabase SQL Editor
├── .gitignore
└── templates/
    ├── base.html           ← shared layout, nav, delete modal
    ├── index.html          ← homepage — all users + file cards
    ├── upload.html         ← upload form with drag & drop
    ├── edit.html           ← edit title / replace thumbnail
    ├── user.html           ← per-user page
    ├── file_detail.html    ← single file detail page
    └── 404.html
```

---

## 🔑 Routes

| Method | Route | What it does |
|--------|-------|-------------|
| GET  | / | Homepage — all users and their files |
| GET  | /user/<username> | Files for one user |
| GET  | /file/<id> | Single file detail page |
| GET  | /upload | Upload form |
| POST | /upload | Save new file to Supabase |
| GET  | /file/<id>/edit | Edit form |
| POST | /file/<id>/edit | Update title / thumbnail |
| POST | /file/<id>/delete | Delete file + storage objects |
| GET  | /api/files | JSON — all files |
| GET  | /api/files/<id> | JSON — one file |
