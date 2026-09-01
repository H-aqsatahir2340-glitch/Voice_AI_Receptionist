# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.chat import router as chat_router
from database import engine
from api.admin import router as admin_router

import models

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AI Receptionist Platform",
    description="Multi-tenant AI Receptionist API",
    version="1.0.0"
)

# ──────────────────────────────────────────────
# CORS Middleware (for web widget)
# ──────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────
app.include_router(chat_router)
app.include_router(admin_router)


@app.get("/")
def root():
    return {
        "service": "AI Receptionist Platform",
        "status": "running",
        "version": "1.0.0"
    }

@app.get("/health")
def health():
    return {"status": "healthy", "database": "connected"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)