# ⚖️ Official Gazette AI Tracker & Compliance Audit System

An automated microservices system that monitors the Turkish Official Gazette (`resmigazete.gov.tr`) daily, inspects the **full text and attached PDF documents** of all published legislations against user-defined keywords, scrapes matched content using Firecrawl, generates compliance summaries using **Google Gemini AI**, dispatches email alerts via Gmail, and maintains a complete audit trail in PostgreSQL.

---

## 🏛️ Architecture & Services

The system runs entirely in Docker containers connected via the `gazette_net` bridge network:

| Service | Technology / Base Image | Port | Responsibility |
| :--- | :--- | :--- | :--- |
| **Database** | `postgres:15-alpine` | `5432` | Stores user preferences (`user_settings`), scan logs (`crawl_logs`), and dispatch history (`notifications_log`). |
| **Workflow & AI Engine** | `docker.n8n.io/n8nio/n8n:latest` | `5678` | CRON trigger (07:00), Firecrawl integration, **Google Gemini LangChain AI Agent** for citizen obligations & risk analysis, and Gmail dispatching. |
| **AI Model** | `Google Gemini API` | Cloud | In-depth legislative impact assessment, tax/penalty detection, obligations, and effective dates. |
| **User Dashboard** | `Python / Streamlit` (`./ui`) | `8501` | Subscription management (UPSERT), real-time profile editing, and detailed audit / AI summary inspection cards. |
| **Scraper** | `Firecrawl API` (Cloud / Self-hosted) | - | Converts daily gazette indices and legislative articles (including PDFs) into LLM-friendly Markdown. |

---

## 🎯 Full-Text & PDF Inspection Logic

Traditional monitoring tools only inspect legislation headlines. However, the most critical changes, liabilities, and fee schedules are often buried deep within individual article clauses or attached PDF schedules.

In this system:
1. Firecrawl crawls each legislation link and downloads associated PDF documents.
2. Content is converted to clean Markdown.
3. User keywords are searched using Turkish character normalization (`i/İ`, `ı/I` mapping and ASCII-folding) across:
   - **`TITLE`**: The legislation headline,
   - **`BODY_TEXT`**: The individual articles and clauses,
   - **`PDF_CONTENT`**: Attached PDF schedules and tables.
4. The exact match location is saved to PostgreSQL audit records under `match_location`.

---

## 🗄️ Database Schema (`init.sql`)

PostgreSQL automatically initializes the following tables on first startup:

- `user_settings`: Subscriber email addresses, keyword arrays (`TEXT[]`), and active status.
- `crawl_logs`: Scanned index date, target URL, total examined items, match count, and crawl status (`SUCCESS`, `IN_PROGRESS`, `FAILED`).
- `notifications_log`: Notification records including legislation title, source URL, match location (`TITLE`, `BODY_TEXT`, `PDF_CONTENT`), generated AI summary, and delivery status (`SENT`, `FAILED`).

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- Docker Engine & Docker Compose (`v2+`)

### 2. Configure Environment Variables
Copy the sample environment file:
```bash
cp .env.example .env
```

Fill in `.env` with your API keys and configuration:
- `FIRECRAWL_API_KEY`: Your Firecrawl API key
- `GEMINI_API_KEY`: Your Google Gemini API key (from Google AI Studio)
- `GMAIL_CLIENT_ID`: OAuth2 Client ID from Google Cloud Console
- `GMAIL_CLIENT_SECRET`: OAuth2 Client Secret from Google Cloud Console
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`: Database credentials

> 💡 **Zero-Touch Automation:** On startup, `init-setup.js` automatically injects PostgreSQL and Google Gemini credentials into n8n and synchronizes the workflow without any manual database setup.

### 3. Start the Services
```bash
docker compose up -d --build
```

Check container status:
```bash
docker compose ps
```

### 4. One-Time Gmail Authorization (Sign in with Google)

> 💡 **Important Note:** The PostgreSQL database, Google Gemini AI, and n8n workflow are **100% automatically configured** from `.env`. Only **Gmail** requires a one-time browser consent due to Google OAuth2 security policies:

1. Open the n8n interface: [`http://localhost:5678`](http://localhost:5678)
2. Go to **Credentials** in the left sidebar (or navigate directly to [`http://localhost:5678/credentials`](http://localhost:5678/credentials)).
3. Click on the pre-created **`Gmail account`** credential (its `Client ID` and `Client Secret` are auto-populated from `.env`).
4. Click the **`Sign in with Google`** button and choose your sender Google account to grant permission.
5. Click **`Save`** at the bottom right.

> ✅ **Persistent Session:** This authorization is performed **only once during initial setup**. The OAuth token is saved on persistent Docker storage (`n8n_data`); it survives container restarts and upgrades.

---

## 🖥️ User Dashboard (Streamlit)

Navigate to `http://localhost:8501` in your browser.

### Tab 1: User & Keyword Subscriptions
- **Any Email Provider Supported:** Gmail is used as the outbound sending engine; recipient subscribers can use Yahoo, Outlook, Gmail, or corporate domain addresses.
- Enter your email address and comma-separated keywords (e.g., `artificial intelligence, crypto assets, minimum wage, vat`).
- **Smart Auto-Fill:** Entering a registered email automatically populates the form with existing keywords and status.
- Submissions perform an `UPSERT` (updates existing record or creates a new one).
- Clicking any subscriber row in the table loads their preferences into the edit form for updating, pausing, or deletion.

### Tab 2: Dispatched Notifications & Audit Log
- **Summary Metrics**: Total alerts dispatched, body/PDF matches, title matches, and successfully delivered emails.
- **Audit Table**: All matched legislations, recipients, match locations (`📄 BODY TEXT`, `📑 PDF CONTENT`, `🏷️ TITLE`), and delivery statuses.
- **Legislation Detail Card**: Select any legislation from the dropdown to inspect its Google Gemini compliance summary, matched keyword, match location, and source link.

---

## ⚡ n8n Workflow & Automation Details

- **Access:** `http://localhost:5678`
- **Workflow File:** [`n8n/workflows/gazette_tracker_workflow.json`](n8n/workflows/gazette_tracker_workflow.json) is imported automatically on startup.
- **Automated Credentials (.env):**
  - **Google Gemini:** `GEMINI_API_KEY` is loaded into n8n on boot.
  - **PostgreSQL:** `gazette_db_cred` is generated on boot matching container credentials.
  - **Gmail OAuth2:** `GMAIL_CLIENT_ID` and `GMAIL_CLIENT_SECRET` are pre-configured.
- **Execution:** Runs automatically every morning at 07:00 (CRON: `0 7 * * *`) or can be triggered manually via the `Test workflow` button in n8n.
