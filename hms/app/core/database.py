from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

db_class = declarative_base()
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
session_maker = sessionmaker(autocommit=False, bind=engine)
