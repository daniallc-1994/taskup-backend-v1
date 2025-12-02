"""
Stripe Payment Handler for TaskUp
Complete implementation with Stripe Connect Express accounts

Business Flow:
1. Customer pays TaskUp (platform) via Payment Intent
2. Money is held in TaskUp's Stripe account (escrow)
3. Tasker must have onboarded via Stripe Connect Express
4. After task completion, TaskUp transfers to tasker's Connect account
5. Platform fee is automatically deducted from transfer
6. Webhooks handle all payment lifecycle events

Credentials:
- All Stripe keys are loaded from environment variables:
  STRIPE_SECRET_KEY
  STRIPE_PUBLISHABLE_KEY
  STRIPE_WEBHOOK_SECRET
"""

import stripe
import os
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)

# Configure Stripe from environment only (NO hardcoded default)
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
if not stripe.api_key:
    raise ValueError("STRIPE_SECRET_KEY not set")

class StripeHandler:
    def __init__(self):
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
        if not self.webhook_secret:
            raise ValueError("STRIPE_WEBHOOK_SECRET not set")

        self.platform_fee_percentage = float(
            os.getenv("PLATFORM_FEE_PERCENTAGE", "10")  # 10% default
        )

        logger.info(
            f"Stripe handler initialized with {self.platform_fee_percentage}% platform fee"
        )

    
    # ============================================
    # CUSTOMER PAYMENTS (Platform receives money)
    # ============================================
    
    def create_payment_intent(
        self,
        amount: int,  # in øre (1 NOK = 100 øre)
        currency: str = "nok",
        user_id: str = None,
        task_id: str = None,
        order_id: str = None,
        customer_email: str = None,
        description: str = None
    ) -> Dict:
        """
        Create a Payment Intent for customer to pay TaskUp
        Money goes directly to TaskUp's Stripe account (platform)
        
        Args:
            amount: Amount in øre (e.g., 50000 = 500 NOK)
            currency: Currency code (default: nok)
            user_id: TaskUp user ID
            task_id: Task ID
            order_id: Order ID for tracking
            customer_email: Customer email
            description: Payment description
        
        Returns:
            Dict with client_secret, payment_intent_id, status
        """
        try:
            metadata = {
                "order_id": order_id,
                "user_id": user_id,
                "task_id": task_id,
                "platform": "taskup"
            }
            
            # Remove None values
            metadata = {k: v for k, v in metadata.items() if v is not None}
            
            payment_intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                description=description or f"TaskUp payment - Order {order_id}",
                metadata=metadata,
                receipt_email=customer_email,
                automatic_payment_methods={
                    'enabled': True,
                    'allow_redirects': 'never'  # Cards only, no bank redirects
                },
                capture_method='automatic',  # Capture immediately
                statement_descriptor='TASKUP',  # Shows on customer's card statement
                statement_descriptor_suffix='TASK',
            )
            
            logger.info(f"Payment Intent created: {payment_intent.id} for {amount} øre")
            
            return {
                "payment_intent_id": payment_intent.id,
                "client_secret": payment_intent.client_secret,
                "status": payment_intent.status,
                "amount": payment_intent.amount,
                "currency": payment_intent.currency
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating payment intent: {e}")
            raise
    
    def get_payment_intent(self, payment_intent_id: str) -> Dict:
        """Get payment intent details"""
        try:
            pi = stripe.PaymentIntent.retrieve(payment_intent_id)
            return {
                "id": pi.id,
                "status": pi.status,
                "amount": pi.amount,
                "currency": pi.currency,
                "metadata": pi.metadata
            }
        except stripe.error.StripeError as e:
            logger.error(f"Error retrieving payment intent: {e}")
            raise
    
    def cancel_payment_intent(self, payment_intent_id: str) -> Dict:
        """Cancel a payment intent (before capture)"""
        try:
            pi = stripe.PaymentIntent.cancel(payment_intent_id)
            logger.info(f"Payment intent cancelled: {payment_intent_id}")
            return {"id": pi.id, "status": pi.status}
        except stripe.error.StripeError as e:
            logger.error(f"Error cancelling payment intent: {e}")
            raise
    
    # ============================================
    # REFUNDS (Return money to customer)
    # ============================================
    
    def create_refund(
        self,
        payment_intent_id: str,
        amount: Optional[int] = None,  # None = full refund
        reason: str = "requested_by_customer",
        metadata: Dict = None
    ) -> Dict:
        """
        Create a refund to customer
        
        Args:
            payment_intent_id: Original payment intent ID
            amount: Amount to refund in øre (None = full refund)
            reason: Refund reason (requested_by_customer, duplicate, fraudulent)
            metadata: Additional metadata
        
        Returns:
            Dict with refund details
        """
        try:
            refund_data = {
                "payment_intent": payment_intent_id,
                "reason": reason,
                "metadata": metadata or {}
            }
            
            if amount:
                refund_data["amount"] = amount
            
            refund = stripe.Refund.create(**refund_data)
            
            logger.info(f"Refund created: {refund.id} for payment {payment_intent_id}")
            
            return {
                "refund_id": refund.id,
                "status": refund.status,
                "amount": refund.amount,
                "currency": refund.currency
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Error creating refund: {e}")
            raise
    
    # ============================================
    # STRIPE CONNECT (Tasker onboarding & payouts)
    # ============================================
    
    def create_connect_account(
        self,
        email: str,
        country: str = "NO",
        user_id: str = None,
        metadata: Dict = None
    ) -> Dict:
        """
        Create a Stripe Connect Express account for tasker
        
        Args:
            email: Tasker's email
            country: Country code (default: NO for Norway)
            user_id: TaskUp user ID
            metadata: Additional metadata
        
        Returns:
            Dict with account_id and onboarding_url
        """
        try:
            account_metadata = metadata or {}
            if user_id:
                account_metadata['taskup_user_id'] = user_id
            
            # Create Express account
            account = stripe.Account.create(
                type='express',
                country=country,
                email=email,
                capabilities={
                    'card_payments': {'requested': True},
                    'transfers': {'requested': True},
                },
                business_type='individual',  # Most taskers are individuals
                metadata=account_metadata,
                settings={
                    'payouts': {
                        'schedule': {
                            'interval': 'manual'  # TaskUp controls when payouts happen
                        }
                    }
                }
            )
            
            # Create account link for onboarding
            account_link = stripe.AccountLink.create(
                account=account.id,
                refresh_url=f"https://taskup.no/connect/refresh?account_id={account.id}",
                return_url=f"https://taskup.no/connect/return?account_id={account.id}",
                type='account_onboarding',
            )
            
            logger.info(f"Connect account created: {account.id}")
            
            return {
                "account_id": account.id,
                "onboarding_url": account_link.url,
                "charges_enabled": account.charges_enabled,
                "payouts_enabled": account.payouts_enabled
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Error creating Connect account: {e}")
            raise
    
    def get_account_status(self, account_id: str) -> Dict:
        """
        Get Connect account status
        
        Returns:
            Dict with charges_enabled, payouts_enabled, requirements
        """
        try:
            account = stripe.Account.retrieve(account_id)
            
            return {
                "account_id": account.id,
                "charges_enabled": account.charges_enabled,
                "payouts_enabled": account.payouts_enabled,
                "details_submitted": account.details_submitted,
                "requirements": {
                    "currently_due": account.requirements.currently_due,
                    "eventually_due": account.requirements.eventually_due,
                    "past_due": account.requirements.past_due,
                },
                "email": account.email
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Error retrieving account: {e}")
            raise
    
    def create_account_link(self, account_id: str) -> str:
        """
        Create a new account link for re-onboarding
        (if tasker needs to complete onboarding or update info)
        """
        try:
            account_link = stripe.AccountLink.create(
                account=account_id,
                refresh_url=f"https://taskup.no/connect/refresh?account_id={account_id}",
                return_url=f"https://taskup.no/connect/return?account_id={account_id}",
                type='account_onboarding',
            )
            
            return account_link.url
            
        except stripe.error.StripeError as e:
            logger.error(f"Error creating account link: {e}")
            raise
    
    # ============================================
    # TRANSFERS (Payout to tasker after completion)
    # ============================================
    
    def transfer_to_tasker(
        self,
        amount: int,  # in øre, BEFORE platform fee
        tasker_account_id: str,
        task_id: str,
        description: str = None
    ) -> Dict:
        """
        Transfer money from TaskUp to tasker's Connect account
        Platform fee is automatically deducted
        
        Example:
            Task budget: 500 NOK = 50000 øre
            Platform fee (10%): 50 NOK = 5000 øre
            Tasker receives: 450 NOK = 45000 øre
        
        Args:
            amount: Total amount in øre (BEFORE fee deduction)
            tasker_account_id: Stripe Connect account ID
            task_id: Task ID
            description: Transfer description
        
        Returns:
            Dict with transfer details
        """
        try:
            # Calculate platform fee
            platform_fee = int(amount * (self.platform_fee_percentage / 100))
            tasker_amount = amount - platform_fee
            
            # Create transfer to tasker
            transfer = stripe.Transfer.create(
                amount=tasker_amount,  # Amount tasker receives (after fee)
                currency='nok',
                destination=tasker_account_id,
                description=description or f"TaskUp payout - Task {task_id}",
                metadata={
                    'task_id': task_id,
                    'original_amount': amount,
                    'platform_fee': platform_fee,
                    'platform_fee_percentage': self.platform_fee_percentage
                }
            )
            
            logger.info(
                f"Transfer created: {transfer.id} | "
                f"Amount: {tasker_amount} øre to tasker | "
                f"Platform fee: {platform_fee} øre ({self.platform_fee_percentage}%)"
            )
            
            return {
                "transfer_id": transfer.id,
                "status": "created",
                "tasker_receives": tasker_amount,
                "platform_fee": platform_fee,
                "total_amount": amount,
                "destination_account": tasker_account_id
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Error creating transfer: {e}")
            raise
    
    def reverse_transfer(
        self,
        transfer_id: str,
        amount: Optional[int] = None,  # None = full reversal
        reason: str = "Task cancelled"
    ) -> Dict:
        """
        Reverse a transfer (take money back from tasker)
        Used if task is cancelled after payout
        """
        try:
            reversal_data = {
                "description": reason,
                "metadata": {"reason": reason}
            }
            
            if amount:
                reversal_data["amount"] = amount
            
            reversal = stripe.Transfer.create_reversal(
                transfer_id,
                **reversal_data
            )
            
            logger.info(f"Transfer reversal created: {reversal.id} for transfer {transfer_id}")
            
            return {
                "reversal_id": reversal.id,
                "status": reversal.status,
                "amount": reversal.amount
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Error reversing transfer: {e}")
            raise
    
    def create_payout(
        self,
        account_id: str,
        amount: int,
        description: str = None
    ) -> Dict:
        """
        Create a payout from tasker's Connect account to their bank
        (Triggers actual money movement to tasker's bank)
        """
        try:
            payout = stripe.Payout.create(
                amount=amount,
                currency='nok',
                description=description or "TaskUp earnings",
                stripe_account=account_id  # Must specify the Connect account
            )
            
            logger.info(f"Payout created: {payout.id} for {amount} øre to account {account_id}")
            
            return {
                "payout_id": payout.id,
                "status": payout.status,
                "amount": payout.amount,
                "arrival_date": payout.arrival_date
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Error creating payout: {e}")
            raise
    
    # ============================================
    # WEBHOOK VALIDATION
    # ============================================
    
    def validate_webhook_signature(
        self,
        payload: bytes,
        signature: str
    ) -> stripe.Event:
        """
        Validate webhook signature and construct event
        
        Args:
            payload: Raw request body (bytes)
            signature: Stripe-Signature header value
        
        Returns:
            Validated Stripe Event object
        
        Raises:
            ValueError: If signature is invalid
        """
        try:
            event = stripe.Webhook.construct_event(
                payload,
                signature,
                self.webhook_secret
            )
            
            logger.info(f"Webhook validated: {event['type']}")
            return event
            
        except ValueError as e:
            logger.error(f"Invalid webhook payload: {e}")
            raise
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {e}")
            raise ValueError("Invalid signature")
    
    # ============================================
    # CUSTOMER MANAGEMENT
    # ============================================
    
    def create_customer(
        self,
        email: str,
        name: str = None,
        user_id: str = None,
        metadata: Dict = None
    ) -> Dict:
        """Create a Stripe customer for saved payment methods"""
        try:
            customer_metadata = metadata or {}
            if user_id:
                customer_metadata['taskup_user_id'] = user_id
            
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=customer_metadata
            )
            
            logger.info(f"Customer created: {customer.id}")
            
            return {
                "customer_id": customer.id,
                "email": customer.email
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Error creating customer: {e}")
            raise
    
    def attach_payment_method(
        self,
        payment_method_id: str,
        customer_id: str
    ) -> Dict:
        """Attach a payment method to a customer"""
        try:
            pm = stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id
            )
            
            logger.info(f"Payment method {payment_method_id} attached to {customer_id}")
            
            return {
                "payment_method_id": pm.id,
                "type": pm.type,
                "card": pm.card if pm.type == 'card' else None
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Error attaching payment method: {e}")
            raise


# ============================================
# FACTORY FUNCTION
# ============================================

def create_stripe_handler() -> StripeHandler:
    """Factory function to create StripeHandler instance"""
    return StripeHandler()


# ============================================
# USAGE EXAMPLES
# ============================================

"""
# Customer pays TaskUp
handler = create_stripe_handler()

# 1. Create payment intent for customer
payment = handler.create_payment_intent(
    amount=50000,  # 500 NOK in øre
    user_id="user_123",
    task_id="task_456",
    order_id="taskup-abc123",
    customer_email="customer@example.com",
    description="Task payment"
)
# Returns: {"client_secret": "pi_xxx_secret_yyy", "payment_intent_id": "pi_xxx"}

# 2. Customer completes payment on frontend using client_secret
# Webhook will notify when payment succeeds

# 3. Tasker onboards to Stripe Connect
connect = handler.create_connect_account(
    email="tasker@example.com",
    user_id="user_789"
)
# Returns: {"account_id": "acct_xxx", "onboarding_url": "https://..."}

# 4. After task is completed, transfer to tasker
transfer = handler.transfer_to_tasker(
    amount=50000,  # 500 NOK (before platform fee)
    tasker_account_id="acct_xxx",
    task_id="task_456",
    description="Task completion payment"
)
# Platform automatically takes 10% fee (50 NOK)
# Tasker receives 450 NOK

# 5. If needed, refund customer
refund = handler.create_refund(
    payment_intent_id="pi_xxx",
    reason="requested_by_customer"
)
"""
