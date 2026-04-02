-- ============================================================
-- Ahilyanagar Mahanagar Palika WhatsApp Bot — DB Schema
-- PostgreSQL 14+
-- ============================================================

-- ── Extensions ──────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── users ────────────────────────────────────────────────────
CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    phone           VARCHAR(20)  NOT NULL UNIQUE,      -- WhatsApp number e.g. 919175675232
    name            VARCHAR(120),                       -- Display name from WA profile
    language        CHAR(2)      NOT NULL DEFAULT 'mr', -- 'en' | 'mr'
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    is_blocked      BOOLEAN      NOT NULL DEFAULT FALSE,
    metadata        JSONB        NOT NULL DEFAULT '{}'
);

CREATE INDEX idx_users_phone ON users(phone);

-- ── sessions ─────────────────────────────────────────────────
-- Tracks current conversation state per user.
-- One active session per user at a time.
CREATE TABLE sessions (
    id              SERIAL PRIMARY KEY,
    user_id         INT          NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    current_node    VARCHAR(80)  NOT NULL DEFAULT 'START',
    previous_node   VARCHAR(80),
    language        CHAR(2)      NOT NULL DEFAULT 'mr',
    context         JSONB        NOT NULL DEFAULT '{}',  -- ward, dept, complaint_text etc.
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    fallback_count  SMALLINT     NOT NULL DEFAULT 0,     -- consecutive invalid inputs
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ  NOT NULL DEFAULT (NOW() + INTERVAL '24 hours')
);

CREATE INDEX idx_sessions_user_active ON sessions(user_id, is_active);
CREATE INDEX idx_sessions_expires     ON sessions(expires_at) WHERE is_active = TRUE;

-- ── complaints ───────────────────────────────────────────────
CREATE TABLE complaints (
    id              SERIAL PRIMARY KEY,
    complaint_id    VARCHAR(20)  NOT NULL UNIQUE,        -- AMP-20260401-0001
    user_id         INT          NOT NULL REFERENCES users(id),
    phone           VARCHAR(20)  NOT NULL,
    ward            VARCHAR(40),                         -- ward_1 … ward_4
    ward_name       VARCHAR(120),
    department      VARCHAR(40),                         -- dept_water, dept_enc …
    dept_name       VARCHAR(120),
    complaint_type  VARCHAR(80),                         -- sub-type id
    complaint_text  TEXT         NOT NULL,
    status          VARCHAR(20)  NOT NULL DEFAULT 'open',
    -- open | acknowledged | in_progress | resolved | closed
    officer_name    VARCHAR(120),
    officer_phone   VARCHAR(20),
    language        CHAR(2)      NOT NULL DEFAULT 'mr',
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ,
    metadata        JSONB        NOT NULL DEFAULT '{}'
);

CREATE INDEX idx_complaints_user      ON complaints(user_id);
CREATE INDEX idx_complaints_status    ON complaints(status);
CREATE INDEX idx_complaints_ward_dept ON complaints(ward, department);
CREATE INDEX idx_complaints_created   ON complaints(created_at DESC);

-- ── messages_log ─────────────────────────────────────────────
-- Full audit trail of every inbound & outbound message.
CREATE TABLE messages_log (
    id              BIGSERIAL PRIMARY KEY,
    wa_message_id   VARCHAR(80)  UNIQUE,                 -- WhatsApp message ID
    user_id         INT          REFERENCES users(id),
    phone           VARCHAR(20)  NOT NULL,
    direction       VARCHAR(4)   NOT NULL CHECK (direction IN ('in', 'out')),
    message_type    VARCHAR(20)  NOT NULL,                -- text | interactive | button
    content         JSONB        NOT NULL DEFAULT '{}',
    node_at_time    VARCHAR(80),
    status          VARCHAR(20)  DEFAULT 'received',      -- received | sent | delivered | read | failed
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_log_user    ON messages_log(user_id, created_at DESC);
CREATE INDEX idx_log_wa_id   ON messages_log(wa_message_id);

-- ── complaint_id sequence + generator ───────────────────────
CREATE SEQUENCE complaint_seq START 1 INCREMENT 1;

CREATE OR REPLACE FUNCTION generate_complaint_id()
RETURNS TEXT LANGUAGE plpgsql AS $$
DECLARE
    seq_val INT;
    today   TEXT;
BEGIN
    seq_val := nextval('complaint_seq');
    today   := TO_CHAR(NOW(), 'YYYYMMDD');
    RETURN 'AMP-' || today || '-' || LPAD(seq_val::TEXT, 4, '0');
END;
$$;

-- ── auto-update updated_at ───────────────────────────────────
CREATE OR REPLACE FUNCTION touch_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$;

CREATE TRIGGER trg_users_updated      BEFORE UPDATE ON users      FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_sessions_updated   BEFORE UPDATE ON sessions   FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_complaints_updated BEFORE UPDATE ON complaints FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- ── sample officer lookup view ───────────────────────────────
CREATE VIEW v_complaint_summary AS
SELECT
    c.complaint_id,
    u.phone,
    u.name       AS citizen_name,
    c.ward_name,
    c.dept_name,
    c.complaint_text,
    c.status,
    c.officer_name,
    c.officer_phone,
    c.created_at,
    c.resolved_at
FROM complaints c
JOIN users u ON u.id = c.user_id
ORDER BY c.created_at DESC;
