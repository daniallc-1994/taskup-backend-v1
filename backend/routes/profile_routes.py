"""
Profile Management Endpoints
Handle profile updates, avatar uploads, and settings
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, EmailStr
from typing import Optional
import os
import uuid
from datetime import datetime
import shutil
from pathlib import Path

router = APIRouter(prefix="/profile", tags=["profile"])


# ============================================
# REQUEST MODELS
# ============================================

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    language: Optional[str] = None
    currency: Optional[str] = None


# ============================================
# UPLOAD AVATAR
# ============================================

@router.post("/upload-avatar")
async def upload_avatar(
    avatar: UploadFile = File(...),
    user_id: str = Form(...),
    # user_id: str = Depends(get_current_user_id)  # Add auth
):
    """
    Upload profile picture
    
    - Accepts: JPG, PNG, WEBP
    - Max size: 5MB
    - Returns: URL to uploaded image
    """
    
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/webp"]
    if avatar.content_type not in allowed_types:
        raise HTTPException(400, "Invalid file type. Use JPG, PNG, or WEBP")
    
    # Validate file size (5MB)
    contents = await avatar.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(400, "File too large. Max 5MB")
    
    # Generate unique filename
    ext = avatar.filename.split('.')[-1]
    filename = f"{user_id}_{uuid.uuid4()}.{ext}"
    
    # Save to local storage (or S3/Supabase Storage)
    upload_dir = Path("uploads/avatars")
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = upload_dir / filename
    
    # Write file
    with open(file_path, "wb") as f:
        f.write(contents)
    
    # Generate URL
    avatar_url = f"/uploads/avatars/{filename}"
    
    # TODO: Update database
    # await supabase.table('profiles').update({
    #     'avatar_url': avatar_url,
    #     'updated_at': datetime.utcnow()
    # }).eq('user_id', user_id).execute()
    
    return {
        "success": True,
        "avatar_url": avatar_url,
        "message": "Profile picture updated successfully"
    }


# ============================================
# UPDATE PROFILE
# ============================================

@router.put("/update")
async def update_profile(
    profile: ProfileUpdate,
    # user_id: str = Depends(get_current_user_id)  # Add auth
):
    """
    Update profile information
    
    Updates any provided fields
    """
    
    # TODO: Update database
    # update_data = profile.dict(exclude_unset=True)
    # update_data['updated_at'] = datetime.utcnow()
    # 
    # result = await supabase.table('profiles').update(
    #     update_data
    # ).eq('user_id', user_id).execute()
    
    return {
        "success": True,
        "message": "Profile updated successfully",
        "profile": profile.dict(exclude_unset=True)
    }


# ============================================
# GET PROFILE
# ============================================

@router.get("/me")
async def get_profile(
    # user_id: str = Depends(get_current_user_id)  # Add auth
):
    """Get current user's profile"""
    
    # TODO: Query database
    # result = await supabase.table('profiles').select(
    #     'id, full_name, email, phone, avatar_url, bio, address, '
    #     'city, country, language, currency, created_at, updated_at'
    # ).eq('user_id', user_id).single().execute()
    
    return {
        "id": "user_123",
        "full_name": "John Doe",
        "email": "john@example.com",
        "phone": "+47 123 45 678",
        "avatar_url": None,
        "bio": "",
        "address": "",
        "city": "Oslo",
        "country": "Norway",
        "language": "nb",
        "currency": "NOK",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }


# ============================================
# DELETE AVATAR
# ============================================

@router.delete("/delete-avatar")
async def delete_avatar(
    # user_id: str = Depends(get_current_user_id)  # Add auth
):
    """Remove profile picture"""
    
    # TODO: Get current avatar URL from database
    # TODO: Delete file from storage
    # TODO: Update database to set avatar_url = null
    
    return {
        "success": True,
        "message": "Profile picture removed"
    }


# ============================================
# AUTO-DETECT LANGUAGE
# ============================================

@router.post("/detect-language")
async def detect_language(
    latitude: float,
    longitude: float
):
    """
    Detect language based on location
    
    Uses reverse geocoding to determine country,
    then returns appropriate language code
    """
    
    # Country to language mapping
    language_map = {
        'NO': 'nb',  # Norway → Norwegian Bokmål
        'SE': 'sv',  # Sweden → Swedish
        'DK': 'da',  # Denmark → Danish
        'FI': 'fi',  # Finland → Finnish
        'DE': 'de',  # Germany → German
        'FR': 'fr',  # France → French
        'ES': 'es',  # Spain → Spanish
        'IT': 'it',  # Italy → Italian
        'NL': 'nl',  # Netherlands → Dutch
        'PL': 'pl',  # Poland → Polish
        'GB': 'en',  # UK → English
        'US': 'en',  # USA → English
    }
    
    try:
        # Use OpenStreetMap Nominatim for reverse geocoding
        import httpx
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://nominatim.openstreetmap.org/reverse",
                params={
                    'lat': latitude,
                    'lon': longitude,
                    'format': 'json'
                },
                headers={'User-Agent': 'TaskUp/1.0'}
            )
            
            data = response.json()
            
            if 'address' in data and 'country_code' in data['address']:
                country_code = data['address']['country_code'].upper()
                language = language_map.get(country_code, 'en')
                
                return {
                    "success": True,
                    "country": data['address'].get('country', 'Unknown'),
                    "country_code": country_code,
                    "language": language,
                    "city": data['address'].get('city') or data['address'].get('town', 'Unknown')
                }
    
    except Exception as e:
        print(f"Error detecting language: {e}")
    
    return {
        "success": False,
        "language": "en",
        "message": "Could not detect location, defaulting to English"
    }
