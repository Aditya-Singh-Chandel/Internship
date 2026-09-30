from fastapi import FastAPI
from app.core.database import engine, db_class
from app.api.routes import tasks

db_class.metadata.create_all(bind=engine)

app = FastAPI(title="Todo API", description="Todo Application")

@app.get("/")
def home():
    return {"message": "this is todo list"}

app.include_router(tasks.router)