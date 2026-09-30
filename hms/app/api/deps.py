from app.core.database import session_maker

def get_db():
    db = session_maker()
    try:
        yield db
    finally:
        db.close()