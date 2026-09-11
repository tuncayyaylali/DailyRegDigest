-- 1. User Settings Table
CREATE TABLE IF NOT EXISTS user_settings (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    keywords TEXT[] NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Crawl & Scraping Audit Logs Table
CREATE TABLE IF NOT EXISTS crawl_logs (
    id SERIAL PRIMARY KEY,
    crawl_date DATE DEFAULT CURRENT_DATE,
    target_url TEXT NOT NULL,
    status VARCHAR(50) NOT NULL, -- 'SUCCESS', 'NO_MATCH', 'FAILED'
    items_scraped_count INT DEFAULT 0,
    matched_count INT DEFAULT 0,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Notifications & AI Summary Archive Table
CREATE TABLE IF NOT EXISTS notifications_log (
    id SERIAL PRIMARY KEY,
    crawl_log_id INT REFERENCES crawl_logs(id) ON DELETE SET NULL,
    recipient_email VARCHAR(255) NOT NULL,
    matched_keyword VARCHAR(100) NOT NULL,
    legislation_title TEXT NOT NULL,
    legislation_url TEXT NOT NULL,
    match_location VARCHAR(50) NOT NULL, -- 'TITLE', 'BODY_TEXT', 'PDF_CONTENT'
    ai_summary TEXT NOT NULL,
    email_status VARCHAR(50) NOT NULL, -- 'SENT', 'FAILED'
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

