# database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("Please set DATABASE_URL in .env")

engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))
Base = declarative_base()

def init_db():
    # Import models here to ensure they're registered
    from models import User, Candidate, Interview, Setting
    Base.metadata.create_all(bind=engine)
