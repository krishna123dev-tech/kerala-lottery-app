import io
import re
import sqlite3
import requests
from bs4 import BeautifulSoup
import pdfplumber

DB_PATH = "lottery.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS draws (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            draw_code TEXT UNIQUE,
            draw_name TEXT,
            draw_date TEXT,
            first_prize TEXT,
            last_three_first_prize TEXT,
            suffix_3digits TEXT
        )
    """)
    conn.commit()
    conn.close()

def parse_pdf_results(pdf_bytes):
    """
    Extracts 1st prize and 3-digit matching suffix numbers from the Kerala Lottery PDF.
    """
    first_prize = None
    three_digit_winners = []
    
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        full_text = "\n".join([page.extract_text() or "" for page in pdf.pages])

    # 1. Extract 1st Prize ticket (Pattern: 2 Letters + 6 Digits, e.g., "AB 123456" or "AB-123456")
    first_prize_match = re.search(r"1st\s+Prize[^\n]*?([A-Z]{2}\s*\d{6})", full_text, re.IGNORECASE)
    if first_prize_match:
        raw_ticket = first_prize_match.group(1).replace(" ", "")
        digits_only = re.search(r"\d{6}", raw_ticket)
        if digits_only:
            first_prize = digits_only.group(0)

    # 2. Extract lower-tier suffix prizes (typically 3 digits)
    # Finds isolated 3-digit groupings in result tables
    candidates = re.findall(r"\b\d{3}\b", full_text)
    # Filter out common false positives like page numbers or year fragments
    three_digit_winners = list(set([c for c in candidates if c not in ["100", "200", "300", "500"]]))

    last_three_fp = first_prize[-3:] if first_prize else None
    return first_prize, last_three_fp, ",".join(three_digit_winners)

def run_scraper():
    init_db()
    portal_url = "https://www.lotteryagent.kerala.gov.in/result/public/"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        res = requests.get(portal_url, headers=headers, timeout=20)
        if res.status_code != 200:
            return {"status": "error", "message": f"HTTP {res.status_code}"}
        
        soup = BeautifulSoup(res.text, "html.parser")
        rows = soup.find_all("tr")
        new_records = 0

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        for row in rows:
            cols = [td.get_text(strip=True) for td in row.find_all("td")]
            pdf_link = row.find("a", href=re.compile(r"\.pdf", re.IGNORECASE))
            
            if len(cols) >= 3 and pdf_link:
                draw_name = cols[0]
                draw_code = cols[1]
                draw_date = cols[2]
                file_url = pdf_link["href"]

                if not file_url.startswith("http"):
                    file_url = "https://www.lotteryagent.kerala.gov.in" + file_url

                cur.execute("SELECT id FROM draws WHERE draw_code = ?", (draw_code,))
                if cur.fetchone():
                    continue  # Already ingested

                # Download PDF
                pdf_res = requests.get(file_url, headers=headers, timeout=20)
                if pdf_res.status_code == 200:
                    fp, last_3_fp, suffixes = parse_pdf_results(pdf_res.content)
                    if fp or suffixes:
                        cur.execute("""
                            INSERT INTO draws (draw_code, draw_name, draw_date, first_prize, last_three_first_prize, suffix_3digits)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (draw_code, draw_name, draw_date, fp, last_3_fp, suffixes))
                        conn.commit()
                        new_records += 1

        conn.close()
        return {"status": "success", "new_records_added": new_records}

    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    print(run_scraper())