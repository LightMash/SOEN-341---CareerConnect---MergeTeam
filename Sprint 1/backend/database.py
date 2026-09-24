#Load .env values
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Every teammate must set DATABASE_URL in their own local .env file (see .env.example).
# Format: postgresql://<user>:<password>@<host>:<port>/<database>
# No default/fallback here on purpose — a silent fallback can hide a missing
# .env and make someone think they're on Postgres when they're not.
SQLALCHEMY_DATABASE_URL = os.environ.get("DATABASE_URL")

#Error Handler (For no .env file)
if not SQLALCHEMY_DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Copy .env.example to .env and fill in your "
        "local PostgreSQL connection string before running the app."
    )

#Error handler (Bad PostgreSQL connection)
if not SQLALCHEMY_DATABASE_URL.startswith("postgresql+pg8000://"):
    raise RuntimeError(
        "DATABASE_URL must be a PostgreSQL connection string "
        "(postgresql+pg8000://user:password@host:port/dbname). "
        f"Got: {SQLALCHEMY_DATABASE_URL!r}"
    )
#Builds connection manager to Supabase
engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
#Creates a factory for database seesions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
#Creates a base class
Base = declarative_base()

#Generator function
def get_db():
    """FastAPI dependency: gives each request its own DB session, closes it after."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

