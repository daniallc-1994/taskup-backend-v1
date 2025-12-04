from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def read_root():
    return {"status": "ok"}


# TEMPORARILY DISABLE ROUTERS TO DEBUG

# from profile.profile_routes import router as profile_router
# app.include_router(profile_router, prefix="/api")

# from auth.auth_routes import router as auth_router
# app.include_router(auth_router, prefix="/api")
