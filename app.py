import threading
import sqlite3
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from scraper import run_scraper, DB_PATH
from analytics import compute_3digit_metrics

app = FastAPI(title="Kerala Lottery 3-Digit Analytics Platform")
templates = Jinja2Templates(directory="templates")

@app.on_event("startup")
def startup_event():
    # Run scraper in a background thread so the web server starts immediately without hanging
    threading.Thread(target=run_scraper, daemon=True).start()

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("SELECT draw_name, draw_code, draw_date, first_prize, last_three_first_prize FROM draws ORDER BY id DESC LIMIT 10")
        recent_draws = cur.fetchall()
    except Exception:
        recent_draws = []
    finally:
        conn.close()

    metrics = compute_3digit_metrics() or {
        "sample_size": 0,
        "hot_combinations": [],
        "hot_suffixes": [],
        "positional_distribution": {"hundreds": {}, "tens": {}, "units": {}}
    }

    return templates.TemplateResponse("index.html", {
        "request": request,
        "recent_draws": recent_draws,
        "metrics": metrics
    })

@app.get("/api/results")
def api_get_results():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("SELECT draw_name, draw_code, draw_date, first_prize, last_three_first_prize FROM draws ORDER BY id DESC LIMIT 50")
        rows = cur.fetchall()
        data = [{"name": r[0], "code": r[1], "date": r[2], "first_prize": r[3], "last_3": r[4]} for r in rows]
    except Exception:
        data = []
    finally:
        conn.close()
    return data

@app.get("/api/predict")
def api_get_prediction():
    metrics = compute_3digit_metrics()
    if not metrics:
        return {"status": "loading", "message": "Scraper is ingesting draws in background. Refresh in 30 seconds."}
    return metrics

@app.post("/api/sync")
def api_trigger_scraper():
    threading.Thread(target=run_scraper, daemon=True).start()
    return {"status": "started", "message": "Scraper job dispatched in background"}
