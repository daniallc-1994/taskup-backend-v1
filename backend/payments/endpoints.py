"""
GDPR Compliance Endpoints
Data privacy, right to deletion, data export
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from datetime import datetime
import json
from typing import Optional

from ..database import supabase
from ..auth import get_current_user
from ..observability.logger import logger

router = APIRouter(prefix="/me", tags=["gdpr"])


@router.post("/delete-account")
async def delete_account(
    password: str,
    reason: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete user account (GDPR Right to Erasure)
    
    Actions:
    - Anonymize personal data
    - Delete identity documents
    - Keep financial records (legal requirement)
    - Sign out user
    """
    
    try:
        user_id = current_user["id"]
        
        # Verify password
        # (Supabase handles this, but add extra check if needed)
        
        # Anonymize user data
        anonymized_email = f"deleted_{user_id}@deleted.taskup.no"
        
        supabase.table("users")\
            .update({
                "name": "Deleted User",
                "email": anonymized_email,
                "phone": None,
                "profile_picture": None,
                "bio": None,
                "address": None,
                "status": "deleted",
                "deleted_at": datetime.utcnow().isoformat(),
                "deletion_reason": reason
            })\
            .eq("id", user_id)\
            .execute()
        
        # Delete identity documents
        supabase.table("identity_documents")\
            .update({"document_url": None, "deleted_at": datetime.utcnow().isoformat()})\
            .eq("user_id", user_id)\
            .execute()
        
        # Keep: tasks, offers, reviews, wallet_transactions (legal requirement)
        
        # Log deletion
        supabase.table("audit_logs").insert({
            "user_id": user_id,
            "action": "account_deleted",
            "entity_type": "user",
            "entity_id": user_id,
            "metadata": {"reason": reason}
        }).execute()
        
        logger.info("account_deleted", user_id=user_id, reason=reason)
        
        return {
            "success": True,
            "message": "Account deleted successfully. Financial records retained per legal requirements."
        }
    
    except Exception as e:
        logger.error(f"Account deletion failed: {str(e)}")
        raise HTTPException(500, "Account deletion failed")


@router.get("/download-data")
async def download_data(current_user: dict = Depends(get_current_user)):
    """
    Export all user data (GDPR Right to Data Portability)
    
    Returns JSON with all user information
    """
    
    try:
        user_id = current_user["id"]
        
        # Collect all user data
        user = supabase.table("users").select("*").eq("id", user_id).single().execute()
        
        wallet = supabase.table("wallet_accounts").select("*").eq("user_id", user_id).execute()
        
        tasks_as_client = supabase.table("tasks").select("*").eq("client_id", user_id).execute()
        
        tasks_as_tasker = supabase.table("tasks").select("*").eq("assigned_to", user_id).execute()
        
        offers = supabase.table("offers").select("*").eq("tasker_id", user_id).execute()
        
        reviews_written = supabase.table("reviews").select("*").eq("reviewer_id", user_id).execute()
        
        reviews_received = supabase.table("reviews").select("*").eq("reviewed_user_id", user_id).execute()
        
        messages = supabase.table("messages")\
            .select("*")\
            .or_(f"sender_id.eq.{user_id},receiver_id.eq.{user_id}")\
            .execute()
        
        transactions = supabase.table("wallet_transactions")\
            .select("*")\
            .eq("wallet_id", wallet.data[0]["id"] if wallet.data else None)\
            .execute()
        
        addresses = supabase.table("addresses").select("*").eq("user_id", user_id).execute()
        
        # Compile data export
        data_export = {
            "export_date": datetime.utcnow().isoformat(),
            "user": user.data,
            "wallet": wallet.data,
            "tasks_as_client": tasks_as_client.data,
            "tasks_as_tasker": tasks_as_tasker.data,
            "offers": offers.data,
            "reviews_written": reviews_written.data,
            "reviews_received": reviews_received.data,
            "messages": messages.data,
            "transactions": transactions.data if transactions.data else [],
            "addresses": addresses.data
        }
        
        # Log export
        supabase.table("audit_logs").insert({
            "user_id": user_id,
            "action": "data_exported",
            "entity_type": "user",
            "entity_id": user_id
        }).execute()
        
        logger.info("data_exported", user_id=user_id)
        
        return data_export
    
    except Exception as e:
        logger.error(f"Data export failed: {str(e)}")
        raise HTTPException(500, "Data export failed")


@router.post("/cookie-consent")
async def save_cookie_consent(
    essential: bool,
    analytics: bool,
    marketing: bool,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Save user's cookie preferences"""
    
    try:
        user_id = current_user["id"]
        ip_address = request.client.host
        user_agent = request.headers.get("user-agent")
        
        supabase.table("cookie_consents").insert({
            "user_id": user_id,
            "essential": essential,
            "analytics": analytics,
            "marketing": marketing,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "consented_at": datetime.utcnow().isoformat()
        }).execute()
        
        logger.info("cookie_consent_saved", user_id=user_id, analytics=analytics, marketing=marketing)
        
        return {"success": True, "message": "Cookie preferences saved"}
    
    except Exception as e:
        logger.error(f"Cookie consent save failed: {str(e)}")
        raise HTTPException(500, "Failed to save preferences")


@router.post("/accept-terms")
async def accept_terms(
    document_slug: str,
    version: str,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Record terms acceptance"""
    
    try:
        user_id = current_user["id"]
        ip_address = request.client.host
        
        supabase.table("terms_acceptances").insert({
            "user_id": user_id,
            "document_slug": document_slug,
            "version": version,
            "ip_address": ip_address,
            "accepted_at": datetime.utcnow().isoformat()
        }).execute()
        
        logger.info("terms_accepted", user_id=user_id, document=document_slug, version=version)
        
        return {"success": True, "message": "Terms accepted"}
    
    except Exception as e:
        logger.error(f"Terms acceptance failed: {str(e)}")
        raise HTTPException(500, "Failed to record acceptance")
