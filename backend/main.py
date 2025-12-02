"""
TaskUp FastAPI Application
Main application file with all routers integrated

This file ties together:
- Payment endpoints (Stripe + Vipps)
- Notification system (Email + SMS)
- AI features
- Admin panel
- GDPR compliance
- Security features
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import routers
from payments.endpoints import router as payments_router
from payments.webhooks import router as webhooks_router
from admin.admin_routes import router as admin_router
from gdpr.gdpr_routes import router as gdpr_router
from observability.health import router as health_router

# Import middleware
from security.rate_limiter import rate_limiter
from security.cors_config import get_cors_origins
from observability.logger import setup_logging
from observability.metrics import setup_metrics

# Initialize logging
setup_logging()

# Create FastAPI app
app = FastAPI(
    title="TaskUp API",
    description="Norway's leading gig economy platform",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS Configuration
origins = get_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate Limiting Middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Apply rate limiting to all requests"""
    if os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true":
        client_ip = request.client.host
        if not rate_limiter.check_rate_limit(client_ip):
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded. Please try again later."}
            )
    
    response = await call_next(request)
    return response

# Setup Metrics
setup_metrics(app)

# ============================================
# REGISTER ROUTERS
# ============================================

# Payment routes - /api/payments/*
app.include_router(payments_router, prefix="/api")

# Webhook routes - /api/webhooks/*
app.include_router(webhooks_router, prefix="/api")

# Admin routes - /api/admin/*
app.include_router(admin_router, prefix="/api")

# GDPR routes - /api/gdpr/*
app.include_router(gdpr_router, prefix="/api")

# Health check - /api/health
app.include_router(health_router, prefix="/api")

# ============================================
# ROOT ENDPOINTS
# ============================================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "TaskUp API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/api/docs"
    }

@app.get("/api")
async def api_root():
    """API root endpoint"""
    return {
        "message": "TaskUp API v1.0.0",
        "endpoints": {
            "payments": "/api/payments",
            "webhooks": "/api/webhooks",
            "admin": "/api/admin",
            "gdpr": "/api/gdpr",
            "health": "/api/health",
            "docs": "/api/docs"
        }
    }

# ============================================
# ERROR HANDLERS
# ============================================

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors"""
    return JSONResponse(
        status_code=404,
        content={"error": "Not found", "path": str(request.url)}
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Handle 500 errors"""
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )

# ============================================
# STARTUP & SHUTDOWN
# ============================================

@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    print("🚀 TaskUp API starting...")
    print(f"📧 Email notifications: {'✅' if os.getenv('SENDGRID_API_KEY') else '❌'}")
    print(f"📱 SMS notifications: {'✅' if os.getenv('TWILIO_ACCOUNT_SID') else '❌'}")
    print(f"🤖 AI features: {'✅' if os.getenv('ANTHROPIC_API_KEY') else '❌'}")
    print(f"💳 Stripe payments: {'✅' if os.getenv('STRIPE_SECRET_KEY') else '❌'}")
    print(f"📊 Sentry monitoring: {'✅' if os.getenv('SENTRY_DSN') else '❌'}")
    print("✅ TaskUp API ready!")

@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown"""
    print("👋 TaskUp API shutting down...")

# ============================================
# RUN APPLICATION
# ============================================

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=True,  # Disable in production
        log_level="info"
    )
