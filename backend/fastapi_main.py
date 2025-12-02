"""
TaskUp FastAPI Application - Production Ready
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import stripe

# Stripe Configuration
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
stripe.api_version = "2023-10-16"

app = FastAPI(
    title="TaskUp API",
    version="1.0.0",
    docs_url="/api/docs"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import routers
try:
    from payments.endpoints import router as payments_router
    app.include_router(payments_router, prefix="/api")
except ImportError as e:
    print(f"⚠️ Payment router: {e}")

try:
    from payments.webhooks import router as webhooks_router
    app.include_router(webhooks_router, prefix="/api")
except ImportError as e:
    print(f"⚠️ Webhook router: {e}")

try:
    from admin.admin_routes import router as admin_router
    app.include_router(admin_router, prefix="/api")
except ImportError as e:
    print(f"⚠️ Admin router: {e}")

try:
    from gdpr.gdpr_routes import router as gdpr_router
    app.include_router(gdpr_router, prefix="/api")
except ImportError as e:
    print(f"⚠️ GDPR router: {e}")

try:
    from observability.health import router as health_router
    app.include_router(health_router, prefix="/api")
except ImportError as e:
    print(f"⚠️ Health router: {e}")

try:
    from profile.profile_routes import router as profile_router
    app.include_router(profile_router, prefix="/api")
    print("✅ Profile router loaded")
except ImportError as e:
    print(f"⚠️ Profile router: {e}")

@app.get("/")
async def root():
    return {"name": "TaskUp API", "status": "running"}

@app.get("/api")
async def api_root():
    return {"message": "TaskUp API v1.0.0", "docs": "/api/docs"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.on_event("startup")
async def startup():
    print("🚀 TaskUp API Ready!")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("fastapi_main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
