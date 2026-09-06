from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import auth as admin_auth
from app.api.admin import labs as admin_labs
from app.api.v1 import auth as v1_auth
from app.api.v1 import challenges as v1_challenges
from app.api.v1 import dashboard as v1_dashboard
from app.api.v1 import me as v1_me
from app.api.v1 import members as v1_members
from app.api.v1 import notifications as v1_notifications
from app.api.v1 import platforms as v1_platforms
from app.api.v1 import progress as v1_progress
from app.api.v1 import reports as v1_reports
from app.api.v1 import semesters as v1_semesters
from app.api.v1 import settings as v1_settings
from app.core.config import settings

app = FastAPI(title="HSLab CTF Classroom API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Super Admin: fully separate namespace, no tenant_id (PRD §3.2).
app.include_router(admin_auth.router)
app.include_router(admin_labs.router)

# Lab-scoped API: every route resolves tenant_id from the verified JWT.
app.include_router(v1_auth.router, prefix="/api/v1")
app.include_router(v1_members.router, prefix="/api/v1")
app.include_router(v1_me.router, prefix="/api/v1")
app.include_router(v1_notifications.router, prefix="/api/v1")
app.include_router(v1_semesters.router, prefix="/api/v1")
app.include_router(v1_challenges.router, prefix="/api/v1")
app.include_router(v1_progress.router, prefix="/api/v1")
app.include_router(v1_platforms.router, prefix="/api/v1")
app.include_router(v1_dashboard.router, prefix="/api/v1")
app.include_router(v1_reports.router, prefix="/api/v1")
app.include_router(v1_settings.router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
