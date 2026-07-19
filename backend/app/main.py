from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import init_db
from .routers import auth, export, history, profile, stream, synth, upload

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Audio Morse Code Translation Platform -- DSP + ML backend API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "project": settings.PROJECT_NAME}


app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(upload.router)
app.include_router(stream.router)
app.include_router(history.router)
app.include_router(export.router)
app.include_router(synth.router)
