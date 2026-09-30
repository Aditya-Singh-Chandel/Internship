import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("DATABASE_CONNECTION_LOCAL")

db_class = declarative_base()
engine = create_engine(db_url)
session_maker = sessionmaker(autocommit=False, bind=engine)