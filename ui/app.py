import os
import time
import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
from datetime import datetime

# Streamlit Page Configuration
st.set_page_config(
    page_title="Official Gazette AI Tracker & Audit Dashboard",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Database Connection Parameters
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "gazette_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

def get_db_connection():
    """Establish a PostgreSQL database connection."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            connect_timeout=5
        )
        return conn
    except Exception as e:
        st.error(f"Database connection error: {e}")
        return None

def fetch_users():
    """Fetch all user settings and subscriptions."""
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, email, keywords, is_active, created_at, updated_at
                FROM user_settings
                ORDER BY updated_at DESC;
            """)
            return cur.fetchall()
    finally:
        conn.close()

def upsert_user(email: str, keywords: list, is_active: bool = True):
    """Insert or update user preferences (UPSERT)."""
    conn = get_db_connection()
    if not conn:
        return False, "Could not connect to database."
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_settings (email, keywords, is_active, updated_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (email) DO UPDATE
                SET keywords = EXCLUDED.keywords,
                    is_active = EXCLUDED.is_active,
                    updated_at = CURRENT_TIMESTAMP;
            """, (email.strip().lower(), keywords, is_active))
            conn.commit()
            return True, "User preferences saved successfully!"
    except Exception as e:
        conn.rollback()
        return False, f"Database error: {e}"
    finally:
        conn.close()

def delete_user(user_id: int):
    """Delete a user subscription record."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM user_settings WHERE id = %s;", (user_id,))
            conn.commit()
            return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()

def fetch_crawl_logs():
    """Fetch crawl and scraping audit logs."""
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, crawl_date, target_url, status, items_scraped_count, matched_count, details, created_at
                FROM crawl_logs
                ORDER BY created_at DESC
                LIMIT 100;
            """)
            return cur.fetchall()
    finally:
        conn.close()

def fetch_notifications_log():
    """Fetch notifications and AI summary archive."""
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, crawl_log_id, recipient_email, matched_keyword, legislation_title, 
                       legislation_url, match_location, ai_summary, email_status, sent_at
                FROM notifications_log
                ORDER BY sent_at DESC
                LIMIT 100;
            """)
            return cur.fetchall()
    finally:
        conn.close()

# --- SIDEBAR ---
with st.sidebar:
    logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
    if os.path.exists(logo_path):
        st.image(logo_path, width=130)
    st.title("Official Gazette AI")
    st.markdown("**Full-Text & PDF Tracker System**")
    st.divider()
    
    st.markdown("""
    **System Architecture:**
    - 🗄️ **PostgreSQL**: Settings & Notification History
    - ⚡ **n8n**: Orchestration & CRON (07:00)
    - 🕷️ **Firecrawl**: Index & Full-Text / PDF Scraping
    - 🧠 **Google Gemini**: Legal Compliance & Risk Analysis
    - 📧 **Gmail**: Automated Personalized Notifications
    """)
    st.caption(f"Database: `{DB_HOST}:{DB_PORT}/{DB_NAME}`")
    
    with st.expander("ℹ️ Gmail Sender Setup", expanded=False):
        st.markdown("""
        **One-Time Gmail Permission:**
        The system sends alerts using Gmail OAuth2.
        
        On initial setup, visit [`localhost:5678`](http://localhost:5678/credentials), open **Gmail account**, and click **'Sign in with Google'** once to grant sender permissions.
        """)

    if st.button("🔄 Refresh Data", use_container_width=True):
        st.rerun()

# --- MAIN TITLE ---
st.title("⚖️ Official Gazette AI Tracker & Audit Dashboard")
st.markdown("Monitors daily gazette legislation, crawls **full text and attached PDF files**, and alerts on keyword matches with AI summaries.")

tab_settings, tab_audit = st.tabs(["⚙️ User & Keyword Subscriptions", "📬 Dispatched Notifications & Audit Log"])

# =========================================================================
# TAB 1: SETTINGS & SUBSCRIPTIONS
# =========================================================================
with tab_settings:
    users = fetch_users()

    # Initialize session state variables
    if "form_version" not in st.session_state:
        st.session_state["form_version"] = 0
    if "form_email" not in st.session_state:
        st.session_state["form_email"] = ""
    if "form_keywords" not in st.session_state:
        st.session_state["form_keywords"] = ""
    if "form_is_active" not in st.session_state:
        st.session_state["form_is_active"] = True
    if "selected_user_id" not in st.session_state:
        st.session_state["selected_user_id"] = None

    # Auto-load keywords when typing a registered email address
    def on_email_input_change():
        curr_ver = st.session_state.get("form_version", 0)
        typed = st.session_state.get(f"widget_email_{curr_ver}", "").strip().lower()
        if not typed:
            return
        found = next((u for u in users if u["email"].lower() == typed), None)
        if found:
            st.session_state["selected_user_id"] = found["id"]
            st.session_state["form_email"] = found["email"]
            st.session_state["form_keywords"] = ", ".join(found["keywords"]) if isinstance(found["keywords"], list) else str(found["keywords"])
            st.session_state["form_is_active"] = bool(found["is_active"])
            st.session_state["form_version"] += 1
            st.toast(f"ℹ️ '{found['email']}' is registered. Existing keywords loaded automatically.")
        else:
            st.session_state["selected_user_id"] = None
            st.session_state["form_email"] = typed

    st.subheader("📌 User Tracking Settings (UPSERT)")
    st.markdown(
        "Specify subscriber email addresses, target keywords, and subscription status. "
        "Entering a registered email address or clicking a row below **automatically populates the form**."
    )

    # Selected user edit banner
    if st.session_state.get("selected_user_id"):
        col_banner, col_del_quick, col_reset = st.columns([2.5, 1, 1])
        with col_banner:
            st.info(f"✏️ **Registered User:** `{st.session_state.get('form_email', '')}` (Edit keywords and save, or delete this user)")
        with col_del_quick:
            if st.button("🗑️ Delete Selected User", type="secondary", use_container_width=True):
                if delete_user(st.session_state["selected_user_id"]):
                    st.success(f"'{st.session_state.get('form_email', '')}' deleted successfully.")
                    st.session_state["selected_user_id"] = None
                    st.session_state["form_email"] = ""
                    st.session_state["form_keywords"] = ""
                    st.session_state["form_is_active"] = True
                    st.session_state["form_version"] += 1
                    time.sleep(0.5)
                    st.rerun()
        with col_reset:
            if st.button("➕ New User Mode", use_container_width=True):
                st.session_state["selected_user_id"] = None
                st.session_state["form_email"] = ""
                st.session_state["form_keywords"] = ""
                st.session_state["form_is_active"] = True
                st.session_state["form_version"] += 1
                st.rerun()

    curr_ver = st.session_state["form_version"]
    col1, col2 = st.columns([2, 1])

    with col1:
        email_input = st.text_input(
            "Email Address",
            value=st.session_state["form_email"],
            key=f"widget_email_{curr_ver}",
            placeholder="user@yahoo.com, user@company.com, or user@gmail.com",
            help="Recipient email for daily alerts. Entering a registered address auto-loads keywords.",
            on_change=on_email_input_change
        )
        keywords_input = st.text_area(
            "Target Keywords (comma-separated)",
            value=st.session_state["form_keywords"],
            key=f"widget_keywords_{curr_ver}",
            placeholder="artificial intelligence, crypto assets, minimum wage, vat, cybersecurity, personal data",
            help="Keywords to match across legislation titles, body articles, and attached PDF documents."
        )
        is_active_input = st.checkbox(
            "Subscription Active (uncheck to pause scanning for this user)", 
            value=st.session_state["form_is_active"],
            key=f"widget_is_active_{curr_ver}"
        )
        
        submit_button = st.button("💾 Save / Update Preferences", use_container_width=True, type="primary")

        if submit_button:
            clean_email = email_input.strip().lower()
            if not clean_email or "@" not in clean_email or "." not in clean_email.split("@")[-1]:
                st.error("Please enter a valid email address.")
            else:
                raw_keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]
                if not raw_keywords:
                    st.error("Please provide at least one target keyword.")
                else:
                    success, message = upsert_user(clean_email, raw_keywords, is_active_input)
                    if success:
                        st.success(message)
                        st.session_state["selected_user_id"] = None
                        st.session_state["form_email"] = ""
                        st.session_state["form_keywords"] = ""
                        st.session_state["form_is_active"] = True
                        st.session_state["form_version"] += 1
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error(message)

    with col2:
        st.info("""
        💡 **Full-Text Search & Smart Form:**
        
        - ⚡ **Auto-Fill:** Entering a registered email automatically populates the form with existing keywords and status.
        - 📬 **Any Email Supported:** Use Yahoo, Gmail, Outlook, or corporate domain addresses as recipients.
        - 📄 **Deep Scanning:** Article text (`BODY_TEXT`), attached PDFs (`PDF_CONTENT`), and titles (`TITLE`) are thoroughly inspected.
        """)

    st.divider()
    st.subheader("👥 Active User Subscriptions")
    st.caption("👇 Click on any **user row** to load their settings into the form above for editing, status toggling, or deletion.")
    
    if users:
        df_users = pd.DataFrame(users)
        df_display = pd.DataFrame({
            "ID": df_users["id"],
            "Email": df_users["email"],
            "Target Keywords": df_users["keywords"].apply(lambda kw: ", ".join(kw) if isinstance(kw, list) else str(kw)),
            "Status": df_users["is_active"].apply(lambda active: "🟢 Active" if active else "🔴 Inactive"),
            "Registered At": pd.to_datetime(df_users["created_at"]).dt.strftime("%Y-%m-%d %H:%M"),
            "Last Updated": pd.to_datetime(df_users["updated_at"]).dt.strftime("%Y-%m-%d %H:%M")
        })

        # Single row selectable dataframe
        event = st.dataframe(
            df_display, 
            use_container_width=True, 
            hide_index=True,
            selection_mode="single-row",
            on_select="rerun"
        )
        
        # When a row is selected from table, fill the form
        if event and hasattr(event, "selection") and event.selection.rows:
            sel_idx = event.selection.rows[0]
            if 0 <= sel_idx < len(users):
                sel_user = users[sel_idx]
                if st.session_state.get("selected_user_id") != sel_user["id"]:
                    st.session_state["selected_user_id"] = sel_user["id"]
                    st.session_state["form_email"] = sel_user["email"]
                    st.session_state["form_keywords"] = ", ".join(sel_user["keywords"]) if isinstance(sel_user["keywords"], list) else str(sel_user["keywords"])
                    st.session_state["form_is_active"] = bool(sel_user["is_active"])
                    st.session_state["form_version"] += 1
                    st.rerun()
        
        # Quick Actions: Delete
        email_options = [u["email"] for u in users]
        current_selected_email = st.session_state.get("form_email", "")
        default_index = 0
        if current_selected_email in email_options:
            default_index = email_options.index(current_selected_email)

        expander_title = f"🗑️ Remove / Delete Subscription: {current_selected_email}" if current_selected_email else "🗑️ Remove / Delete Subscription"
        with st.expander(expander_title, expanded=bool(st.session_state.get("selected_user_id"))):
            del_user_email = st.selectbox(
                "Select User to Delete:", 
                options=email_options,
                index=default_index,
                key=f"del_user_select_{st.session_state['form_version']}"
            )
            if st.button("Delete Selected User", type="secondary", use_container_width=True):
                selected_user = next((u for u in users if u["email"] == del_user_email), None)
                if selected_user and delete_user(selected_user["id"]):
                    st.success(f"{del_user_email} deleted successfully.")
                    st.session_state["selected_user_id"] = None
                    st.session_state["form_email"] = ""
                    st.session_state["form_keywords"] = ""
                    st.session_state["form_is_active"] = True
                    st.session_state["form_version"] += 1
                    time.sleep(0.5)
                    st.rerun()
    else:
        st.warning("No registered users found yet. Add one using the form above.")

# =========================================
# TAB 2: DISPATCHED NOTIFICATIONS & AUDIT LOG
# =========================================================================
with tab_audit:
    notifications = fetch_notifications_log()

    # Top Summary Metrics
    total_notifications = len(notifications)
    body_matches = sum(1 for n in notifications if n.get("match_location") in ("BODY_TEXT", "PDF_CONTENT"))
    title_matches = sum(1 for n in notifications if n.get("match_location") == "TITLE")
    sent_count = sum(1 for n in notifications if n.get("email_status") == "SENT")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Alerts", total_notifications)
    m2.metric("Body / PDF Matches", body_matches, help="Matched inside article body text or PDF attachments rather than just the title")
    m3.metric("Title Matches", title_matches, help="Matched directly in the legislation title")
    m4.metric("Delivered Emails", f"✅ {sent_count}")

    st.divider()

    # Initialize selected notification state if not set
    if "selected_notification_id" not in st.session_state:
        st.session_state["selected_notification_id"] = notifications[0]["id"] if notifications else None

    # Dispatched Notifications & Matches (Full Width)
    st.subheader("📬 Dispatched Notifications & Audit Log")
    st.caption("👇 Click on any **legislation row** in the table below to automatically view its AI summary and legal impact report.")
    
    if notifications:
        df_notif = pd.DataFrame(notifications)
        
        def format_location(loc):
            if loc == "BODY_TEXT":
                return "📄 BODY TEXT"
            elif loc == "PDF_CONTENT":
                return "📑 PDF CONTENT"
            elif loc == "TITLE":
                return "🏷️ TITLE"
            return str(loc)

        df_notif_display = pd.DataFrame({
            "ID": df_notif["id"],
            "Recipient Email": df_notif["recipient_email"],
            "Matched Keyword": df_notif["matched_keyword"],
            "Match Location": df_notif["match_location"].apply(format_location),
            "Legislation Title": df_notif["legislation_title"],
            "Status": df_notif["email_status"].apply(lambda s: f"✅ {s}" if s == "SENT" else f"❌ {s}"),
            "Date": pd.to_datetime(df_notif["sent_at"]).dt.strftime("%Y-%m-%d %H:%M")
        })

        notif_event = st.dataframe(
            df_notif_display, 
            use_container_width=True, 
            hide_index=True,
            selection_mode="single-row",
            on_select="rerun"
        )

        # When a row is clicked/selected in the table, sync session state
        if notif_event and hasattr(notif_event, "selection") and notif_event.selection.rows:
            sel_row_idx = notif_event.selection.rows[0]
            if 0 <= sel_row_idx < len(notifications):
                st.session_state["selected_notification_id"] = notifications[sel_row_idx]["id"]
    else:
        st.info("No dispatched notification records found yet.")

    st.divider()

    # Selected Legislation Detail Card
    st.subheader("🔍 Legislation Review & AI Summary Card")
    
    if notifications:
        options = {
            f"ID #{n['id']} - {n['legislation_title'][:70]}... ({n['matched_keyword']})": n
            for n in notifications
        }
        option_keys = list(options.keys())

        # Determine index of currently selected notification
        default_index = 0
        current_selected_id = st.session_state.get("selected_notification_id")
        for idx, n in enumerate(notifications):
            if n["id"] == current_selected_id:
                default_index = idx
                break

        selected_key = st.selectbox(
            "Select a legislation record to inspect:", 
            options=option_keys,
            index=default_index,
            key=f"select_notif_box_{current_selected_id}"
        )
        selected_item = options[selected_key]
        st.session_state["selected_notification_id"] = selected_item["id"]

        # Location badge format
        loc = selected_item["match_location"]
        loc_badge = "📄 Found in Body Text" if loc == "BODY_TEXT" else ("📑 Found in PDF Content" if loc == "PDF_CONTENT" else "🏷️ Found in Title")

        with st.container(border=True):
            head_col1, head_col2 = st.columns([3, 1])
            with head_col1:
                st.markdown(f"### 📜 {selected_item['legislation_title']}")
            with head_col2:
                st.info(f"**Location:** {loc_badge}")

            meta_c1, meta_c2, meta_c3 = st.columns(3)
            meta_c1.markdown(f"**🎯 Matched Keyword:** `{selected_item['matched_keyword']}`")
            meta_c2.markdown(f"**👤 Recipient:** `{selected_item['recipient_email']}`")
            meta_c3.markdown(f"**⏰ Sent At:** {selected_item['sent_at']}")

            st.markdown(f"🔗 **Official Gazette Source Link:** [{selected_item['legislation_url']}]({selected_item['legislation_url']})")

            st.markdown("#### 🤖 AI Legislation Summary & Impact Analysis (Google Gemini)")
            with st.container(border=True):
                st.markdown(selected_item['ai_summary'])
    else:
        st.markdown("_Selectable review cards will be available once notifications are recorded._")

