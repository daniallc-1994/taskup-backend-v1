# TaskUp FastAPI Backend
# Complete API for Business, Wallet, FAQ, Legal, Addresses
# Requirements: pip install fastapi uvicorn supabase python-jose passlib python-multipart

from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
import os
from supabase import create_client, Client
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="TaskUp API",
    description="Complete backend for TaskUp platform",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production: specific domains only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # Service key for backend
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Security
security = HTTPBearer()


# =====================================================
# ENUMS
# =====================================================

class BusinessStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class CompanySize(str, Enum):
    SIZE_1_10 = "1-10"
    SIZE_11_50 = "11-50"
    SIZE_51_200 = "51-200"
    SIZE_201_500 = "201-500"
    SIZE_501_PLUS = "501+"

class TransactionType(str, Enum):
    DEPOSIT = "deposit"
    HOLD = "hold"
    RELEASE = "release"
    REFUND = "refund"
    CASHBACK = "cashback"
    PAYOUT = "payout"
    ADJUSTMENT = "adjustment"

class TransactionDirection(str, Enum):
    CREDIT = "credit"
    DEBIT = "debit"

class TransactionStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# =====================================================
# PYDANTIC MODELS
# =====================================================

# Business Profile Models
class BusinessProfileCreate(BaseModel):
    organisation_name: str = Field(..., min_length=2, max_length=200)
    work_email: EmailStr
    industry: str = Field(..., min_length=2, max_length=100)
    company_size: CompanySize
    business_registration_number: str = Field(..., min_length=9, max_length=9)  # Norwegian org number
    street: str = Field(..., min_length=2, max_length=200)
    postcode: str = Field(..., min_length=4, max_length=10)
    city: str = Field(..., min_length=2, max_length=100)
    country: str = Field(default="Norway", max_length=100)

class BusinessProfileUpdate(BaseModel):
    organisation_name: Optional[str] = None
    work_email: Optional[EmailStr] = None
    industry: Optional[str] = None
    company_size: Optional[CompanySize] = None
    business_registration_number: Optional[str] = None
    street: Optional[str] = None
    postcode: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None

class BusinessProfileApproval(BaseModel):
    status: BusinessStatus
    rejection_reason: Optional[str] = None

# Wallet Models
class WalletResponse(BaseModel):
    id: str
    user_id: str
    balance: float
    currency: str
    total_deposited: float
    total_withdrawn: float
    total_earned: float
    total_spent: float
    total_cashback: float
    created_at: datetime

class TransactionCreate(BaseModel):
    task_id: Optional[str] = None
    type: TransactionType
    amount: float = Field(..., gt=0)
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = {}

# Address Models
class AddressCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=50)
    street: str = Field(..., min_length=2, max_length=200)
    postcode: str = Field(..., min_length=4, max_length=10)
    city: str = Field(..., min_length=2, max_length=100)
    country: str = Field(default="Norway", max_length=100)
    lat: Optional[float] = None
    lng: Optional[float] = None
    is_default: bool = False

class AddressUpdate(BaseModel):
    label: Optional[str] = None
    street: Optional[str] = None
    postcode: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    is_default: Optional[bool] = None

# FAQ Models
class FAQResponse(BaseModel):
    id: str
    category: str
    question: str
    answer: str
    language: str
    sort_order: int

# Legal Document Models
class LegalDocumentResponse(BaseModel):
    id: str
    slug: str
    title: str
    content: str
    language: str
    version: str
    published_at: datetime


# =====================================================
# AUTHENTICATION
# =====================================================

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token and get current user"""
    try:
        token = credentials.credentials
        # Verify token with Supabase
        user = supabase.auth.get_user(token)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
        return user
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

async def get_current_user_id(user = Depends(get_current_user)) -> str:
    """Extract user ID from authenticated user"""
    # Get user record from database
    result = supabase.table("users").select("id").eq("auth_id", user.user.id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")
    return result.data["id"]

async def get_admin_user(user = Depends(get_current_user)):
    """Verify user is admin"""
    result = supabase.table("users").select("role").eq("auth_id", user.user.id).single().execute()
    if not result.data or result.data.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# =====================================================
# BUSINESS PROFILES ENDPOINTS
# =====================================================

@app.post("/business-profiles", status_code=status.HTTP_201_CREATED)
async def create_business_profile(
    profile: BusinessProfileCreate,
    user_id: str = Depends(get_current_user_id)
):
    """Create business/pro registration"""
    try:
        # Check if user already has business profile
        existing = supabase.table("business_profiles")\
            .select("id")\
            .eq("user_id", user_id)\
            .execute()
        
        if existing.data:
            raise HTTPException(status_code=400, detail="Business profile already exists")
        
        # Create business profile
        result = supabase.table("business_profiles").insert({
            "user_id": user_id,
            **profile.dict()
        }).execute()
        
        logger.info(f"Business profile created for user {user_id}")
        return result.data[0]
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating business profile: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create business profile")


@app.get("/business-profiles/me")
async def get_my_business_profile(user_id: str = Depends(get_current_user_id)):
    """Get current user's business profile"""
    try:
        result = supabase.table("business_profiles")\
            .select("*")\
            .eq("user_id", user_id)\
            .single()\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Business profile not found")
        
        return result.data
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching business profile: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch business profile")


@app.put("/business-profiles/me")
async def update_my_business_profile(
    profile: BusinessProfileUpdate,
    user_id: str = Depends(get_current_user_id)
):
    """Update current user's business profile (only if pending)"""
    try:
        # Check status
        existing = supabase.table("business_profiles")\
            .select("status")\
            .eq("user_id", user_id)\
            .single()\
            .execute()
        
        if not existing.data:
            raise HTTPException(status_code=404, detail="Business profile not found")
        
        if existing.data["status"] != "pending":
            raise HTTPException(status_code=400, detail="Can only update pending profiles")
        
        # Update
        updates = {k: v for k, v in profile.dict().items() if v is not None}
        result = supabase.table("business_profiles")\
            .update(updates)\
            .eq("user_id", user_id)\
            .execute()
        
        logger.info(f"Business profile updated for user {user_id}")
        return result.data[0]
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating business profile: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update business profile")


@app.get("/admin/business-profiles")
async def list_business_profiles(
    status: Optional[BusinessStatus] = None,
    limit: int = 50,
    offset: int = 0,
    admin = Depends(get_admin_user)
):
    """Admin: List all business profiles with optional filter"""
    try:
        query = supabase.table("business_profiles").select("*")
        
        if status:
            query = query.eq("status", status.value)
        
        result = query.order("created_at", desc=True)\
            .range(offset, offset + limit - 1)\
            .execute()
        
        return result.data
    
    except Exception as e:
        logger.error(f"Error listing business profiles: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list business profiles")


@app.put("/admin/business-profiles/{profile_id}")
async def approve_reject_business_profile(
    profile_id: str,
    approval: BusinessProfileApproval,
    admin = Depends(get_admin_user)
):
    """Admin: Approve or reject business profile"""
    try:
        # Get admin user ID
        admin_result = supabase.table("users")\
            .select("id")\
            .eq("auth_id", admin.user.id)\
            .single()\
            .execute()
        admin_id = admin_result.data["id"]
        
        # Update business profile
        updates = {
            "status": approval.status.value,
            "reviewed_at": datetime.utcnow().isoformat(),
            "reviewed_by": admin_id
        }
        
        if approval.rejection_reason:
            updates["rejection_reason"] = approval.rejection_reason
        
        result = supabase.table("business_profiles")\
            .update(updates)\
            .eq("id", profile_id)\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Business profile not found")
        
        # If approved, update user role to 'business'
        if approval.status == BusinessStatus.APPROVED:
            profile = result.data[0]
            supabase.table("users")\
                .update({"role": "business"})\
                .eq("id", profile["user_id"])\
                .execute()
        
        logger.info(f"Business profile {profile_id} {approval.status.value} by admin {admin_id}")
        return result.data[0]
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating business profile: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update business profile")


# =====================================================
# WALLET ENDPOINTS
# =====================================================

@app.get("/wallet/me", response_model=WalletResponse)
async def get_my_wallet(user_id: str = Depends(get_current_user_id)):
    """Get current user's wallet"""
    try:
        result = supabase.table("wallet_accounts")\
            .select("*")\
            .eq("user_id", user_id)\
            .single()\
            .execute()
        
        if not result.data:
            # Create wallet if doesn't exist
            create_result = supabase.table("wallet_accounts")\
                .insert({"user_id": user_id})\
                .execute()
            return create_result.data[0]
        
        return result.data
    
    except Exception as e:
        logger.error(f"Error fetching wallet: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch wallet")


@app.get("/wallet/me/transactions")
async def get_my_transactions(
    limit: int = 50,
    offset: int = 0,
    user_id: str = Depends(get_current_user_id)
):
    """Get current user's transaction history"""
    try:
        # Get wallet ID
        wallet = supabase.table("wallet_accounts")\
            .select("id")\
            .eq("user_id", user_id)\
            .single()\
            .execute()
        
        if not wallet.data:
            return []
        
        # Get transactions
        result = supabase.table("wallet_transactions")\
            .select("*")\
            .eq("wallet_id", wallet.data["id"])\
            .order("created_at", desc=True)\
            .range(offset, offset + limit - 1)\
            .execute()
        
        return result.data
    
    except Exception as e:
        logger.error(f"Error fetching transactions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch transactions")


@app.post("/wallet/tasks/{task_id}/hold")
async def hold_task_payment(
    task_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """Hold payment in escrow when customer pays for task"""
    try:
        # Get task details
        task = supabase.table("tasks")\
            .select("budget, client_id")\
            .eq("id", task_id)\
            .single()\
            .execute()
        
        if not task.data:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Verify user is the client
        if task.data["client_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        # Get wallet
        wallet = supabase.table("wallet_accounts")\
            .select("id")\
            .eq("user_id", user_id)\
            .single()\
            .execute()
        
        if not wallet.data:
            raise HTTPException(status_code=404, detail="Wallet not found")
        
        # Calculate amounts
        task_amount = float(task.data["budget"]) / 100  # Convert cents to NOK
        service_fee = task_amount * 0.15  # 15% service fee
        total_amount = task_amount + service_fee
        
        # Create hold transaction via RPC
        result = supabase.rpc("create_wallet_transaction", {
            "p_wallet_id": wallet.data["id"],
            "p_task_id": task_id,
            "p_type": "hold",
            "p_amount": total_amount,
            "p_direction": "debit",
            "p_description": f"Payment held for task {task_id}",
            "p_metadata": {
                "task_amount": task_amount,
                "service_fee": service_fee,
                "total_amount": total_amount
            }
        }).execute()
        
        logger.info(f"Payment held for task {task_id}: {total_amount} NOK")
        return {
            "transaction_id": result.data,
            "task_id": task_id,
            "amount_held": total_amount,
            "message": "Payment held in escrow until task completion"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error holding payment: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to hold payment")


@app.post("/wallet/tasks/{task_id}/release")
async def release_task_payment(
    task_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """Release payment from escrow to tasker when task completed"""
    try:
        # Get task details
        task = supabase.table("tasks")\
            .select("budget, client_id, assigned_to, status")\
            .eq("id", task_id)\
            .single()\
            .execute()
        
        if not task.data:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Verify user is the client
        if task.data["client_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        # Verify task is completed
        if task.data["status"] != "completed":
            raise HTTPException(status_code=400, detail="Task not completed yet")
        
        # Get tasker's wallet
        tasker_wallet = supabase.table("wallet_accounts")\
            .select("id")\
            .eq("user_id", task.data["assigned_to"])\
            .single()\
            .execute()
        
        if not tasker_wallet.data:
            raise HTTPException(status_code=404, detail="Tasker wallet not found")
        
        # Calculate amount (task price without service fee)
        task_amount = float(task.data["budget"]) / 100  # Convert cents to NOK
        
        # Release payment to tasker
        result = supabase.rpc("create_wallet_transaction", {
            "p_wallet_id": tasker_wallet.data["id"],
            "p_task_id": task_id,
            "p_type": "release",
            "p_amount": task_amount,
            "p_direction": "credit",
            "p_description": f"Payment released for task {task_id}",
            "p_metadata": {"task_id": task_id}
        }).execute()
        
        # Calculate cashback (2% of task amount)
        cashback_amount = task_amount * 0.02
        
        # Give cashback to customer
        customer_wallet = supabase.table("wallet_accounts")\
            .select("id")\
            .eq("user_id", user_id)\
            .single()\
            .execute()
        
        if customer_wallet.data:
            supabase.rpc("create_wallet_transaction", {
                "p_wallet_id": customer_wallet.data["id"],
                "p_task_id": task_id,
                "p_type": "cashback",
                "p_amount": cashback_amount,
                "p_direction": "credit",
                "p_description": f"2% cashback for task {task_id}",
                "p_metadata": {"task_id": task_id}
            }).execute()
        
        logger.info(f"Payment released for task {task_id}: {task_amount} NOK + {cashback_amount} cashback")
        return {
            "transaction_id": result.data,
            "task_id": task_id,
            "amount_released": task_amount,
            "cashback": cashback_amount,
            "message": "Payment released to tasker successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error releasing payment: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to release payment")


@app.post("/wallet/tasks/{task_id}/refund")
async def refund_task_payment(
    task_id: str,
    reason: str,
    user_id: str = Depends(get_current_user_id)
):
    """Refund payment to customer if task cancelled or disputed"""
    try:
        # Get task details
        task = supabase.table("tasks")\
            .select("budget, client_id, status")\
            .eq("id", task_id)\
            .single()\
            .execute()
        
        if not task.data:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Verify user is the client or admin
        # (In production, add admin check here)
        if task.data["client_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        # Get customer's wallet
        customer_wallet = supabase.table("wallet_accounts")\
            .select("id")\
            .eq("user_id", task.data["client_id"])\
            .single()\
            .execute()
        
        if not customer_wallet.data:
            raise HTTPException(status_code=404, detail="Wallet not found")
        
        # Calculate refund (task amount, not including service fee)
        task_amount = float(task.data["budget"]) / 100  # Convert cents to NOK
        
        # Create refund transaction
        result = supabase.rpc("create_wallet_transaction", {
            "p_wallet_id": customer_wallet.data["id"],
            "p_task_id": task_id,
            "p_type": "refund",
            "p_amount": task_amount,
            "p_direction": "credit",
            "p_description": f"Refund for task {task_id}: {reason}",
            "p_metadata": {"task_id": task_id, "reason": reason}
        }).execute()
        
        logger.info(f"Payment refunded for task {task_id}: {task_amount} NOK")
        return {
            "transaction_id": result.data,
            "task_id": task_id,
            "amount_refunded": task_amount,
            "message": "Payment refunded to TaskUp Wallet"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refunding payment: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to refund payment")


# =====================================================
# ADDRESS ENDPOINTS
# =====================================================

@app.get("/me/addresses")
async def get_my_addresses(user_id: str = Depends(get_current_user_id)):
    """Get all saved addresses for current user"""
    try:
        result = supabase.table("user_addresses")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("is_default", desc=True)\
            .order("created_at", desc=True)\
            .execute()
        
        return result.data
    
    except Exception as e:
        logger.error(f"Error fetching addresses: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch addresses")


@app.post("/me/addresses", status_code=status.HTTP_201_CREATED)
async def create_address(
    address: AddressCreate,
    user_id: str = Depends(get_current_user_id)
):
    """Create new saved address"""
    try:
        result = supabase.table("user_addresses").insert({
            "user_id": user_id,
            **address.dict()
        }).execute()
        
        logger.info(f"Address created for user {user_id}")
        return result.data[0]
    
    except Exception as e:
        logger.error(f"Error creating address: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create address")


@app.put("/me/addresses/{address_id}")
async def update_address(
    address_id: str,
    address: AddressUpdate,
    user_id: str = Depends(get_current_user_id)
):
    """Update saved address"""
    try:
        # Verify ownership
        existing = supabase.table("user_addresses")\
            .select("id")\
            .eq("id", address_id)\
            .eq("user_id", user_id)\
            .single()\
            .execute()
        
        if not existing.data:
            raise HTTPException(status_code=404, detail="Address not found")
        
        # Update
        updates = {k: v for k, v in address.dict().items() if v is not None}
        result = supabase.table("user_addresses")\
            .update(updates)\
            .eq("id", address_id)\
            .execute()
        
        logger.info(f"Address {address_id} updated")
        return result.data[0]
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating address: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update address")


@app.delete("/me/addresses/{address_id}")
async def delete_address(
    address_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """Delete saved address"""
    try:
        result = supabase.table("user_addresses")\
            .delete()\
            .eq("id", address_id)\
            .eq("user_id", user_id)\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Address not found")
        
        logger.info(f"Address {address_id} deleted")
        return {"message": "Address deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting address: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete address")


@app.post("/me/addresses/{address_id}/set-default")
async def set_default_address(
    address_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """Set address as default"""
    try:
        # Verify ownership
        existing = supabase.table("user_addresses")\
            .select("id")\
            .eq("id", address_id)\
            .eq("user_id", user_id)\
            .single()\
            .execute()
        
        if not existing.data:
            raise HTTPException(status_code=404, detail="Address not found")
        
        # Update (trigger will handle unsetting other defaults)
        result = supabase.table("user_addresses")\
            .update({"is_default": True})\
            .eq("id", address_id)\
            .execute()
        
        logger.info(f"Address {address_id} set as default")
        return result.data[0]
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting default address: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to set default address")


# =====================================================
# FAQ ENDPOINTS
# =====================================================

@app.get("/faq", response_model=List[FAQResponse])
async def get_faqs(language: str = "en"):
    """Get all active FAQs grouped by category"""
    try:
        result = supabase.table("faqs")\
            .select("*")\
            .eq("language", language)\
            .eq("is_active", True)\
            .order("category")\
            .order("sort_order")\
            .execute()
        
        return result.data
    
    except Exception as e:
        logger.error(f"Error fetching FAQs: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch FAQs")


# =====================================================
# LEGAL DOCUMENTS ENDPOINTS
# =====================================================

@app.get("/legal/{slug}", response_model=LegalDocumentResponse)
async def get_legal_document(slug: str, language: str = "en"):
    """Get legal document by slug (terms, privacy, etc.)"""
    try:
        result = supabase.table("legal_documents")\
            .select("*")\
            .eq("slug", slug)\
            .eq("language", language)\
            .eq("is_active", True)\
            .order("published_at", desc=True)\
            .limit(1)\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Legal document not found")
        
        return result.data[0]
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching legal document: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch legal document")


# =====================================================
# HEALTH CHECK
# =====================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }


# =====================================================
# RUN SERVER
# =====================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
