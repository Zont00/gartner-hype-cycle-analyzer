import aiosqlite
from pathlib import Path

DATABASE_PATH = Path(__file__).parent.parent.parent / "data" / "hype_cycle.db"

async def get_db():
    """Async context manager for database connections"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row  # Access columns by name
        yield db

async def init_db():
    """Initialize database schema"""
    DATABASE_PATH.parent.mkdir(exist_ok=True)  # Ensure data/ exists

    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                phase TEXT NOT NULL,
                confidence REAL,
                reasoning TEXT,
                social_data TEXT,
                papers_data TEXT,
                patents_data TEXT,
                news_data TEXT,
                finance_data TEXT,
                expires_at TIMESTAMP
            )
        """)

        # MIGRATION: Add per_source_analyses_data column if it doesn't exist
        cursor = await db.execute("PRAGMA table_info(analyses)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]

        if "per_source_analyses_data" not in column_names:
            await db.execute("ALTER TABLE analyses ADD COLUMN per_source_analyses_data TEXT")

        # MIGRATION: Add query expansion columns if they don't exist
        if "query_expansion_applied" not in column_names:
            await db.execute("ALTER TABLE analyses ADD COLUMN query_expansion_applied INTEGER DEFAULT 0")

        if "expanded_terms_data" not in column_names:
            await db.execute("ALTER TABLE analyses ADD COLUMN expanded_terms_data TEXT")

        await db.execute("CREATE INDEX IF NOT EXISTS idx_keyword ON analyses(keyword)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_expires ON analyses(expires_at)")
        await db.commit()
