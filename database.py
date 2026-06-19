import os
import bcrypt
import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.environ.get("DATABASE_URL", "")

def get_conn():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    statements = [
        """CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            nama VARCHAR(100) NOT NULL,
            sandi_hash VARCHAR(255) NOT NULL,
            role VARCHAR(10) NOT NULL DEFAULT 'viewer' CHECK (role IN ('admin','viewer')),
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS research_data (
            id SERIAL PRIMARY KEY,
            nama_ibu VARCHAR(150) NOT NULL,
            pekerjaan VARCHAR(150),
            yang_dirasakan TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS feedback (
            id SERIAL PRIMARY KEY,
            nama_ibu VARCHAR(150) NOT NULL,
            pengalaman TEXT,
            perasaan_setelah TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS gallery_photos (
            id SERIAL PRIMARY KEY,
            filename VARCHAR(255) NOT NULL,
            deskripsi TEXT,
            uploaded_by VARCHAR(100),
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS videos (
            id SERIAL PRIMARY KEY,
            fitur_id INTEGER NOT NULL,
            judul VARCHAR(200) NOT NULL,
            judul_en VARCHAR(200),
            durasi VARCHAR(20),
            filename VARCHAR(255),
            source_type VARCHAR(10) NOT NULL DEFAULT 'upload',
            youtube_id VARCHAR(20),
            urutan INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
    ]
    for stmt in statements:
        cur.execute(stmt)

    # Migration: tambah kolom baru jika tabel videos sudah ada dari versi lama
    migration_statements = [
        "ALTER TABLE videos ALTER COLUMN filename DROP NOT NULL",
        "ALTER TABLE videos ADD COLUMN IF NOT EXISTS source_type VARCHAR(10) NOT NULL DEFAULT 'upload'",
        "ALTER TABLE videos ADD COLUMN IF NOT EXISTS youtube_id VARCHAR(20)",
    ]
    for stmt in migration_statements:
        try:
            cur.execute(stmt)
        except Exception as e:
            conn.rollback()
            print(f"⚠️ Migration skip: {e}")
        else:
            conn.commit()

    # Seed admin default jika belum ada
    cur.execute("SELECT COUNT(*) as c FROM users WHERE role='admin'")
    row = cur.fetchone()
    if row['c'] == 0:
        hashed = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()
        cur.execute(
            "INSERT INTO users (nama, sandi_hash, role) VALUES (%s, %s, 'admin')",
            ("Admin", hashed)
        )

    conn.commit()
    cur.close()
    conn.close()
    print("✅ DB initialized")