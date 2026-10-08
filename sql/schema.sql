PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS channel (
    channel_id TEXT PRIMARY KEY,
    channel_name TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS campaign (
    campaign_id TEXT PRIMARY KEY,
    cobrand_partner TEXT,
    campaign_name TEXT
);

CREATE TABLE IF NOT EXISTS customer (
    customer_id TEXT PRIMARY KEY,
    first_seen_at TEXT,
    last_seen_at TEXT,
    n_transactions INTEGER,
    total_spend INTEGER
);

CREATE TABLE IF NOT EXISTS pricing (
    pricing_id TEXT PRIMARY KEY,
    price INTEGER NOT NULL,
    price_band TEXT,
    first_seen_at TEXT
);

CREATE TABLE IF NOT EXISTS device_profile (
    device_id TEXT PRIMARY KEY,
    platform TEXT,
    is_mobile INTEGER,
    model TEXT,
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS transaction_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_key TEXT NOT NULL UNIQUE,
    source_file TEXT NOT NULL,
    channel_id TEXT NOT NULL REFERENCES channel(channel_id),
    campaign_id TEXT REFERENCES campaign(campaign_id),
    customer_id TEXT REFERENCES customer(customer_id),
    pricing_id TEXT REFERENCES pricing(pricing_id),
    device_id TEXT REFERENCES device_profile(device_id),
    transaction_id TEXT,
    detail_id TEXT,
    callback_url TEXT,
    status_activated TEXT NOT NULL CHECK (status_activated IN ('ACTIVE','CANCEL','PENDING','FAILED')),
    psn TEXT,
    redeem_code TEXT,
    bill_number TEXT,
    price INTEGER,
    is_revenue_valid INTEGER NOT NULL DEFAULT 0,
    subscription_start_date TEXT,
    subscription_expired_at TEXT,
    subscription_cancel_date TEXT,
    duration_days INTEGER,
    is_churn INTEGER NOT NULL DEFAULT 0,
    puid TEXT,
    pin TEXT,
    email TEXT,
    referral_code TEXT,
    user_agent TEXT,
    ip TEXT,
    created_at TEXT,
    updated_at TEXT,
    deleted_at TEXT,
    is_test INTEGER NOT NULL DEFAULT 0,
    ingested_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_log_channel ON transaction_log(channel_id);
CREATE INDEX IF NOT EXISTS idx_log_status ON transaction_log(status_activated);
CREATE INDEX IF NOT EXISTS idx_log_customer ON transaction_log(customer_id);
