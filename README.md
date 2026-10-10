# Delhi High Court Income Tax Judgment Scraper and Notifier

This system scrapes the Delhi High Court website for judgments, filters for final judgments related to income tax (excluding interim/procedural orders), and sends these judgments to the user via Telegram on a daily basis at 4:00 PM IST.

## Features
- Scrapes Delhi High Court judgments website
- Filters for final judgments (excludes interim/procedural orders)
- Identifies income tax-related cases using keyword matching
- Prevents duplicate notifications using persistent storage
- Sends daily Telegram notifications with judgment details
- Robust error handling and logging
- Ready for cloud deployment on **Render** (Free Web Service or native Cron Job)

---

## Deploying on Render (Step-by-Step Guide)

You can run this scraper 24/7 on [Render](https://render.com). Because daily scheduled scrapers can be hosted on Render in two ways, choose the option that fits your plan:

- **Option A (100% Free):** Render Free Web Service + free scheduled trigger from [cron-job.org](https://cron-job.org).
- **Option B (Paid Plan):** Native Render Cron Job running directly at 4:00 PM IST (10:30 UTC).

---

### Step 1: Push Project to GitHub

Render deploys directly from a GitHub repository.

1. Open PowerShell / Command Prompt in this folder:
   ```powershell
   cd "c:\Users\Monu\Desktop\DHC jugements"
   ```
2. Initialize git and commit:
   ```bash
   git init
   git add .
   git commit -m "Delhi High Court scraper ready for Render deployment"
   ```
3. Create a new repository on [GitHub](https://github.com/new) (e.g. `dhc-judgment-scraper`).
4. Link and push your code:
   ```bash
   git branch -M main
   git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/dhc-judgment-scraper.git
   git push -u origin main
   ```

---

### Step 2: Setup on Render

#### Option A: Deploy as Free Web Service (Recommended - Free Tier)

1. Sign up or log in to [dashboard.render.com](https://dashboard.render.com).
2. Click **New +** -> **Web Service**.
3. Connect your GitHub repository (`dhc-judgment-scraper`).
4. Fill in the deployment settings:
   - **Name:** `dhc-judgment-scraper`
   - **Language / Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
   - **Instance Type:** `Free`
5. Under **Environment Variables**, add:
   - `TELEGRAM_BOT_TOKEN` = `your_bot_token_here`
   - `TELEGRAM_CHAT_ID` = `your_chat_id_here`
   - `FORCE_RUN` = `true`
   - *(Optional)* `CRON_SECRET` = `your_chosen_random_secret` (to prevent unauthorized triggers)
6. Click **Deploy Web Service**.
7. Once deployed, Render will provide a public URL like:
   `https://dhc-judgment-scraper.onrender.com`
8. You can visit `https://dhc-judgment-scraper.onrender.com` in your browser to view the dashboard and logs, or test scraping by visiting `/run`.

##### Schedule Daily Runs with Free Cron (cron-job.org):
Because Render free web services sleep when idle, use a free cron service to trigger it daily at 4:00 PM IST:
1. Create a free account at [cron-job.org](https://cron-job.org).
2. Click **Create Cronjob**.
3. **URL:** `https://dhc-judgment-scraper.onrender.com/run` (or `https://dhc-judgment-scraper.onrender.com/run?secret=YOUR_CRON_SECRET` if secret is set).
4. **Schedule:** Every day at `16:00` (select Timezone: `Asia/Kolkata` or `10:30` UTC).
5. Save the job. Every day at 4:00 PM IST, cron-job.org will wake your Render app, run the scraper, send Telegram alerts, and finish!

---

#### Option B: Deploy as Native Render Cron Job (Paid Starter Plan)

If you have a paid Render account:
1. In Render Dashboard, click **New +** -> **Cron Job**.
2. Connect your repository.
3. Configure settings:
   - **Name:** `dhc-scraper-cron`
   - **Runtime:** `Python`
   - **Schedule:** `30 10 * * *` *(runs at 10:30 UTC = 4:00 PM IST every day)*
   - **Build Command:** `pip install -r requirements.txt`
   - **Command:** `python main.py --force`
4. Set Environment Variables:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
5. Click **Create Cron Job**.

---

### Important Note on State Persistence & Duplicates

On Render, the container filesystem is ephemeral (resets on restart or redeployment).
- `storage.py` writes sent judgment IDs to `sent_judgments.json`.
- If you attach a persistent disk (Render paid plan), set `STORAGE_FILE=/var/data/sent_judgments.json`.
- On the free plan, recent judgments within the scraping window are filtered. For permanent cloud storage without disks, you can store IDs in a free database (like Neon, Supabase, or Upstash Redis).

---

## Local Setup & Usage

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Telegram Bot
1. Open Telegram and search for `@BotFather`.
2. Send `/newbot` and follow the prompts to get your bot token.
3. Obtain your Chat ID by messaging `@getmyid_bot` or your bot.

### 3. Set Local Environment Variables
```powershell
$env:TELEGRAM_BOT_TOKEN="your_bot_token_here"
$env:TELEGRAM_CHAT_ID="your_chat_id_here"
```

### 4. Run Locally
- **Test run immediately (bypassing time check):**
  ```bash
  python main.py --force
  ```
- **Run the local web dashboard:**
  ```bash
  python app.py
  ```
- **Scheduled run (4:00 PM IST):**
  ```bash
  python main.py
  ```

---

## File Structure
- `app.py`: Web service for Render (dashboard, healthcheck, `/run` webhook trigger)
- `main.py`: Core orchestrator script (scrapes, filters, deduplicates, notifies)
- `scraper.py`: Fetches and filters Delhi High Court judgments
- `notifier.py`: Sends notifications via Telegram Bot API (HTTP requests)
- `storage.py`: Manages sent judgments tracking to prevent duplicate notifications
- `render.yaml`: Render Blueprint configuration file
- `requirements.txt`: Python package requirements
- `run.bat`: Quick Windows launcher