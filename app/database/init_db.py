"""Explicit development-only database initialization; never called on application startup."""
from app.database.connection import Base, engine
from app.database import models  # noqa: F401 - registers all mapped tables

if __name__ == "__main__":
    Base.metadata.create_all(engine)
    print("CARELINK database tables created (existing data was preserved).")
