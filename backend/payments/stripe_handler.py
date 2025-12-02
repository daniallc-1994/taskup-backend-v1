"""
Stripe Payment Handler
Complete integration with Stripe Payment Intents + Connect
Supports: Payments, refunds, payouts to taskers
"""

import stripe
from typing import Optional, Dict, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class StripeHandler:
    """Handle Stripe payments and payouts for TaskUp"""
    
    def __init__(self, secret_key: str, webhook_secret: str):
        stripe.api_key = secret_key
        self.webhook_secret = webhook_secret
    
    async def create_payment_intent(
        self,
        amount: int,  # Amount in NOK
        user_id: str,
        order_id: str,
        description: str = "TaskUp payment",
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Create a Stripe Payment Intent
        
        Args:
            amount: Amount in NOK (will be converted to øre/cents)
            user_id: TaskUp user ID
            order_id: Unique order ID for idempotency
            description: Payment description
            metadata: Additional data to attach
        
        Returns:
            Dict with client_secret, payment_intent_id, etc.
        """
        try:
            # Merge metadata
            payment_metadata = {
                "user_id": user_id,
                "order_id": order_id,
                "platform": "taskup"
            }
            if metadata:
                payment_metadata.update(metadata)
            
            # Create payment intent
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert NOK to øre
                currency='nok',
                description=description,
                metadata=payment_metadata,
                automatic_payment_methods={'enabled': True},
                idempotency_key=f"taskup-{order_id}"  # Prevent duplicates
            )
            
            logger.info(f"Stripe Payment Intent created: {intent.id}, {amount} NOK")
            
            return {
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id,
                "amount": amount,
                "status": intent.status
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe Payment Intent creation failed: {str(e)}")
            raise Exception(f"Stripe payment failed: {str(e)}")
    
    async def get_payment_intent(self, payment_intent_id: str) -> Dict[str, Any]:
        """Get payment intent details"""
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            return {
                "id": intent.id,
                "amount": intent.amount / 100,  # øre to NOK
                "status": intent.status,
                "metadata": intent.metadata,
                "created": intent.created
            }
        except stripe.error.StripeError as e:
            logger.error(f"Failed to retrieve Payment Intent: {str(e)}")
            raise Exception(f"Stripe query failed: {str(e)}")
    
    async def confirm_payment_intent(self, payment_intent_id: str) -> Dict[str, Any]:
        """
        Confirm a payment intent (if not auto-confirmed)
        """
        try:
            intent = stripe.PaymentIntent.confirm(payment_intent_id)
            logger.info(f"Payment Intent confirmed: {intent.id}")
            return {
                "id": intent.id,
                "status": intent.status
            }
        except stripe.error.StripeError as e:
            logger.error(f"Payment confirmation failed: {str(e)}")
            raise Exception(f"Stripe confirmation failed: {str(e)}")
    
    async def cancel_payment_intent(
        self,
        payment_intent_id: str,
        cancellation_reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Cancel a payment intent"""
        try:
            intent = stripe.PaymentIntent.cancel(
                payment_intent_id,
                cancellation_reason=cancellation_reason
            )
            logger.info(f"Payment Intent cancelled: {intent.id}")
            return {
                "id": intent.id,
                "status": intent.status
            }
        except stripe.error.StripeError as e:
            logger.error(f"Payment cancellation failed: {str(e)}")
            raise Exception(f"Stripe cancellation failed: {str(e)}")
    
    async def create_refund(
        self,
        payment_intent_id: str,
        amount: Optional[int] = None,  # Amount in NOK, None = full refund
        reason: str = "requested_by_customer",
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Refund a payment
        
        Args:
            payment_intent_id: Original payment intent ID
            amount: Amount to refund in NOK (None = full refund)
            reason: One of: duplicate, fraudulent, requested_by_customer
            metadata: Additional data
        """
        try:
            refund_params = {
                "payment_intent": payment_intent_id,
                "reason": reason
            }
            
            if amount is not None:
                refund_params["amount"] = int(amount * 100)  # NOK to øre
            
            if metadata:
                refund_params["metadata"] = metadata
            
            refund = stripe.Refund.create(**refund_params)
            
            logger.info(f"Stripe refund created: {refund.id}, {refund.amount/100} NOK")
            
            return {
                "refund_id": refund.id,
                "amount": refund.amount / 100,
                "status": refund.status,
                "payment_intent": payment_intent_id
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe refund failed: {str(e)}")
            raise Exception(f"Stripe refund failed: {str(e)}")
    
    # ============================================
    # STRIPE CONNECT - Payouts to Taskers
    # ============================================
    
    async def create_connected_account(
        self,
        email: str,
        country: str = "NO",
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Create a Stripe Connect Express account for a tasker
        
        Returns:
            Dict with account_id and onboarding_url
        """
        try:
            account = stripe.Account.create(
                type='express',
                country=country,
                email=email,
                capabilities={
                    'card_payments': {'requested': True},
                    'transfers': {'requested': True}
                },
                metadata=metadata or {}
            )
            
            # Create account link for onboarding
            account_link = stripe.AccountLink.create(
                account=account.id,
                refresh_url='https://taskup.no/settings/payout/refresh',
                return_url='https://taskup.no/settings/payout/complete',
                type='account_onboarding'
            )
            
            logger.info(f"Stripe Connect account created: {account.id}")
            
            return {
                "account_id": account.id,
                "onboarding_url": account_link.url,
                "status": "created"
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create Connect account: {str(e)}")
            raise Exception(f"Stripe Connect creation failed: {str(e)}")
    
    async def get_account_status(self, account_id: str) -> Dict[str, Any]:
        """Check if tasker has completed Connect onboarding"""
        try:
            account = stripe.Account.retrieve(account_id)
            
            return {
                "account_id": account.id,
                "charges_enabled": account.charges_enabled,
                "payouts_enabled": account.payouts_enabled,
                "details_submitted": account.details_submitted,
                "requirements": account.requirements
            }
        except stripe.error.StripeError as e:
            logger.error(f"Failed to retrieve account status: {str(e)}")
            raise Exception(f"Stripe account query failed: {str(e)}")
    
    async def create_payout(
        self,
        amount: int,  # Amount in NOK
        destination_account_id: str,
        description: str,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Transfer money to tasker's Connect account
        
        Args:
            amount: Amount in NOK
            destination_account_id: Tasker's Stripe Connect account ID
            description: Payout description
            metadata: Additional data
        """
        try:
            transfer = stripe.Transfer.create(
                amount=int(amount * 100),  # NOK to øre
                currency='nok',
                destination=destination_account_id,
                description=description,
                metadata=metadata or {}
            )
            
            logger.info(f"Stripe payout created: {transfer.id}, {amount} NOK")
            
            return {
                "transfer_id": transfer.id,
                "amount": amount,
                "destination": destination_account_id,
                "status": "succeeded"
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe payout failed: {str(e)}")
            raise Exception(f"Stripe payout failed: {str(e)}")
    
    async def reverse_transfer(
        self,
        transfer_id: str,
        amount: Optional[int] = None  # NOK, None = full reversal
    ) -> Dict[str, Any]:
        """
        Reverse a transfer (e.g., in dispute resolution)
        """
        try:
            reversal_params = {"transfer": transfer_id}
            
            if amount is not None:
                reversal_params["amount"] = int(amount * 100)
            
            reversal = stripe.Transfer.create_reversal(**reversal_params)
            
            logger.info(f"Transfer reversed: {reversal.id}")
            
            return {
                "reversal_id": reversal.id,
                "amount": reversal.amount / 100,
                "status": "succeeded"
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Transfer reversal failed: {str(e)}")
            raise Exception(f"Transfer reversal failed: {str(e)}")
    
    # ============================================
    # WEBHOOK VALIDATION
    # ============================================
    
    def validate_webhook_signature(
        self,
        payload: bytes,
        signature_header: str
    ) -> Optional[stripe.Event]:
        """
        Validate Stripe webhook signature and return event
        
        Args:
            payload: Raw request body (bytes)
            signature_header: Stripe-Signature header
        
        Returns:
            stripe.Event if valid, None if invalid
        """
        try:
            event = stripe.Webhook.construct_event(
                payload,
                signature_header,
                self.webhook_secret
            )
            return event
            
        except ValueError:
            # Invalid payload
            logger.error("Invalid webhook payload")
            return None
        except stripe.error.SignatureVerificationError:
            # Invalid signature
            logger.error("Invalid webhook signature")
            return None
    
    # ============================================
    # CUSTOMER MANAGEMENT
    # ============================================
    
    async def create_customer(
        self,
        email: str,
        name: str,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Create a Stripe customer (for saved payment methods)
        """
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            
            logger.info(f"Stripe customer created: {customer.id}")
            
            return {
                "customer_id": customer.id,
                "email": email
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create customer: {str(e)}")
            raise Exception(f"Stripe customer creation failed: {str(e)}")
    
    async def attach_payment_method(
        self,
        payment_method_id: str,
        customer_id: str
    ) -> Dict[str, Any]:
        """
        Attach a payment method to a customer (for future use)
        """
        try:
            payment_method = stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id
            )
            
            logger.info(f"Payment method attached: {payment_method.id}")
            
            return {
                "payment_method_id": payment_method.id,
                "type": payment_method.type,
                "card": payment_method.card if hasattr(payment_method, 'card') else None
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to attach payment method: {str(e)}")
            raise Exception(f"Payment method attachment failed: {str(e)}")
    
    async def list_payment_methods(self, customer_id: str) -> list:
        """Get all payment methods for a customer"""
        try:
            payment_methods = stripe.PaymentMethod.list(
                customer=customer_id,
                type='card'
            )
            
            return [
                {
                    "id": pm.id,
                    "type": pm.type,
                    "card": {
                        "brand": pm.card.brand,
                        "last4": pm.card.last4,
                        "exp_month": pm.card.exp_month,
                        "exp_year": pm.card.exp_year
                    } if pm.card else None
                }
                for pm in payment_methods.data
            ]
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to list payment methods: {str(e)}")
            return []


# Convenience function
def create_stripe_handler() -> StripeHandler:
    """
    Create StripeHandler with credentials from environment variables
    """
    import os
    
    return StripeHandler(
        secret_key=os.getenv("STRIPE_SECRET_KEY"),
        webhook_secret=os.getenv("STRIPE_WEBHOOK_SECRET")
    )
