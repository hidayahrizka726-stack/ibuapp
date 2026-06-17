import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from database import init_db
from routers.api import router

app = FastAPI(title="ArdiyaMidly")

@app.on_event("startup")
def startup():
    init_db()

app.include_router(router)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/{full_path:path}")
def spa(full_path: str):
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
