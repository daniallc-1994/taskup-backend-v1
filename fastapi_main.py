from fastapi import FastAPI

from profile.profile_routes import router as profile_router
from auth.auth_routes import router as auth_router

app = FastAPI()


@app.get("/")
async def read_root():
    return {"status": "ok"}


# Routers must be added AFTER app is created
app.include_router(profile_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
