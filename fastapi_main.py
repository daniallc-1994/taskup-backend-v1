from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from profile.profile_routes import router as profile_router
from auth.auth_routes import router as auth_router

app = FastAPI()

# CORS for frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "https://taskup.no",
        "https://taskup-frontend.vercel.app",
        "https://www.taskup.no",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def read_root():
    return {"status": "ok"}


# Routers must be added AFTER app is created
app.include_router(profile_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
