from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import Base, SessionLocal, engine
from app.integrations import google_sheets
from app.routers import admin, auth, export, manager, meta, public, reports, shifts
from app.schema_migrations import ensure_users_is_approved_column
from app.seed import repair_demo_passwords, seed_if_empty


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_users_is_approved_column()
    db = SessionLocal()
    try:
        seed_if_empty(db)
        repair_demo_passwords(db)
    finally:
        db.close()
    yield


app = FastAPI(title="График смен", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(public.router)
app.include_router(auth.router)
app.include_router(manager.router)
app.include_router(shifts.router)
app.include_router(reports.router)
app.include_router(export.router)
app.include_router(meta.router)
app.include_router(admin.router)
app.include_router(google_sheets.router)

static_dir = Path(__file__).resolve().parent.parent / "static"
if static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
def index():
    index_path = Path(__file__).resolve().parent.parent / "static" / "index.html"
    if index_path.is_file():
        return FileResponse(index_path)
    return {"message": "Положите index.html в папку static/"}
