#!/usr/bin/env python3
"""
Web service interface for Delhi High Court Income Tax Judgment Scraper.
Designed for deployment on Render (Web Service).
Provides health check and web triggers for free-tier cron scheduling.
"""
import os
import sys
import logging
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, render_template_string

# Import scraping logic
from main import run_scraper, IST_OFFSET, RUN_START_TIME, RUN_END_TIME
from notifier import TelegramNotifier

app = Flask(__name__)
logger = logging.getLogger("app")

# HTML template for the root status dashboard
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Delhi High Court Judgment Scraper</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #0f172a; color: #f8fafc; padding: 2rem; margin: 0; }
        .card { max-width: 650px; margin: 0 auto; background: #1e293b; border-radius: 12px; padding: 2rem; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3); border: 1px solid #334155; }
        h1 { color: #38bdf8; margin-top: 0; font-size: 1.5rem; }
        .badge { display: inline-block; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.85rem; font-weight: 600; background: #065f46; color: #34d399; }
        .info { margin: 1.5rem 0; font-size: 0.95rem; line-height: 1.6; }
        .info p { margin: 0.5rem 0; }
        .btn { display: inline-block; background: #0284c7; color: white; padding: 0.6rem 1.2rem; border-radius: 6px; text-decoration: none; font-weight: 500; cursor: pointer; border: none; }
        .btn:hover { background: #0369a1; }
        .logs-box { margin-top: 1.5rem; background: #0b0f19; padding: 1rem; border-radius: 8px; font-family: monospace; font-size: 0.8rem; max-height: 250px; overflow-y: auto; color: #94a3b8; white-space: pre-wrap; }
    </style>
</head>
<body>
    <div class="card">
        <h1>Delhi High Court Judgment Scraper</h1>
        <span class="badge">Service Running</span>
        <div class="info">
            <p><strong>Current Server UTC Time:</strong> {{ utc_time }}</p>
            <p><strong>Current IST Time:</strong> {{ ist_time }}</p>
            <p><strong>Target Daily Schedule:</strong> 4:00 PM IST (10:30 UTC)</p>
            <p><strong>Status:</strong> Scraper ready</p>
        </div>
        <form action="/run" method="post" style="display:inline;">
            <button type="submit" class="btn">Trigger Scraper Now</button>
        </form>
        <a href="/test-telegram" class="btn" style="background:#10b981; margin-left:0.5rem;">Test Telegram Bot</a>
        <a href="/logs" class="btn" style="background:#475569; margin-left:0.5rem;">View Raw Logs</a>
        
        <h3>Recent Logs</h3>
        <div class="logs-box">{{ recent_logs }}</div>
    </div>
</body>
</html>
"""

def get_recent_logs(lines: int = 50) -> str:
    """Read the last N lines of judgment_scraper.log"""
    log_file = "judgment_scraper.log"
    if not os.path.exists(log_file):
        return "No log file found yet."
    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()
            return "".join(all_lines[-lines:])
    except Exception as e:
        return f"Error reading logs: {e}"

@app.route("/", methods=["GET"])
def index():
    """Health check and status dashboard"""
    now_utc = datetime.utcnow()
    now_ist = now_utc + IST_OFFSET
    return render_template_string(
        HTML_TEMPLATE,
        utc_time=now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
        ist_time=now_ist.strftime("%Y-%m-%d %H:%M:%S IST"),
        recent_logs=get_recent_logs(30)
    )

@app.route("/health", methods=["GET"])
def health():
    """Simple JSON healthcheck endpoint for Render"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }), 200

@app.route("/run", methods=["GET", "POST"])
def trigger_run():
    """
    Webhook endpoint to trigger scraping.
    Can be pinged by cron services (like cron-job.org) daily at 4:00 PM IST.
    Supports optional secret verification via CRON_SECRET env var.
    """
    cron_secret = os.getenv("CRON_SECRET")
    if cron_secret:
        # Check Authorization header or query param
        auth_header = request.headers.get("Authorization", "").replace("Bearer ", "")
        param_token = request.args.get("secret", "")
        if auth_header != cron_secret and param_token != cron_secret:
            return jsonify({"error": "Unauthorized"}), 401

    # Force execution regardless of exact 5-minute time window when pinged via webhook
    force = request.args.get("force", "true").lower() in ("1", "true", "yes")
    result = run_scraper(force=force)
    return jsonify(result), 200

@app.route("/test-telegram", methods=["GET", "POST"])
def test_telegram():
    """Test endpoint to verify Telegram credentials and deliver a test message"""
    notifier = TelegramNotifier()
    result = notifier.send_test_message()
    return jsonify(result), 200 if result.get("ok") else 400

@app.route("/logs", methods=["GET"])
def logs():
    """Endpoint to inspect recent scraper logs"""
    return get_recent_logs(100), 200, {"Content-Type": "text/plain; charset=utf-8"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
