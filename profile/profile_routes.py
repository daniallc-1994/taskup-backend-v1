from fastapi import APIRouter

router = APIRouter()

@router.get("/profile/ping")
async def profile_ping():
    return {"status": "ok"}
