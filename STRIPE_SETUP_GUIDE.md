# 🎯 STRIPE INTEGRATION - COMPLETE SETUP GUIDE
**For TaskUp with Stripe Connect**

---

## ✅ CREDENTIALS CONFIGURED

Your Stripe account is ready:

**Live API Keys:**
```bash
STRIPE_SECRET_KEY=sk_live_your_real_key_here
STRIPE_PUBLISHABLE_KEY=pk_live_your_real_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_real_key_here
```

**Webhook URL:**
```
https://taskup.no/api/webhooks/stripe
```

---

## 🔄 BUSINESS FLOW (EXACTLY AS SPECIFIED)

### **1. Customer Payment (Customer → TaskUp)**

```python
# Customer pays for a task
from payments.stripe_handler_complete import create_stripe_handler

handler = create_stripe_handler()

# Create payment intent
payment = handler.create_payment_intent(
    amount=50000,  # 500 NOK = 50000 øre
    user_id="user_123",
    task_id="task_456",
    order_id="taskup-abc123",
    customer_email="customer@taskup.no",
    description="Task: Fix plumbing issue"
)

# Returns:
{
    "client_secret": "pi_xxx_secret_yyy",  # Send to frontend
    "payment_intent_id": "pi_xxx",
    "status": "requires_payment_method"
}
```

**Frontend (React):**
```typescript
import { PaymentElement, useStripe, useElements } from '@stripe/react-stripe-js';

// In your component
const stripe = useStripe();
const elements = useElements();

const handleSubmit = async (e) => {
  e.preventDefault();
  
  const {error, paymentIntent} = await stripe.confirmPayment({
    elements,
    confirmParams: {
      return_url: 'https://taskup.no/payment/success',
    },
  });
  
  if (paymentIntent.status === 'succeeded') {
    // Payment successful!
    // Webhook will handle backend updates
  }
};
```

**What Happens:**
- ✅ Money goes to TaskUp's Stripe account
- ✅ Held in TaskUp's balance (escrow)
- ✅ Webhook `payment_intent.succeeded` fires
- ✅ Task status → `in_progress`
- ✅ Chat unlocked for client & tasker

---

### **2. Tasker Onboarding (Tasker → Stripe Connect)**

```python
# Tasker signs up and needs to onboard
connect = handler.create_connect_account(
    email="tasker@gmail.com",
    country="NO",
    user_id="user_789",
    metadata={"taskup_role": "tasker"}
)

# Returns:
{
    "account_id": "acct_xxx",
    "onboarding_url": "https://connect.stripe.com/setup/e/acct_xxx/...",
    "charges_enabled": False,
    "payouts_enabled": False
}
```

**Frontend:**
```typescript
// Redirect tasker to onboarding
window.location.href = onboarding_url;

// Tasker completes:
// 1. Personal information
// 2. Bank account details
// 3. Identity verification

// After completion, webhook 'account.updated' fires
// charges_enabled: true, payouts_enabled: true
```

**Return URLs:**
```
Success: https://taskup.no/connect/return?account_id=acct_xxx
Refresh: https://taskup.no/connect/refresh?account_id=acct_xxx
```

---

### **3. Task Completion & Payout (TaskUp → Tasker)**

```python
# Task is marked as completed by client
# Transfer money from TaskUp to tasker

transfer = handler.transfer_to_tasker(
    amount=50000,  # 500 NOK total (BEFORE fee)
    tasker_account_id="acct_xxx",
    task_id="task_456",
    description="Task completion payment"
)

# Returns:
{
    "transfer_id": "tr_xxx",
    "tasker_receives": 45000,      # 450 NOK (after 10% fee)
    "platform_fee": 5000,          # 50 NOK (10%)
    "total_amount": 50000          # 500 NOK
}
```

**What Happens:**
- ✅ 450 NOK → Tasker's Stripe balance
- ✅ 50 NOK → TaskUp (platform fee)
- ✅ Webhook `transfer.created` fires
- ✅ Webhook `transfer.paid` fires
- ✅ Task status → `completed`

**Money is now in tasker's Stripe balance, ready to payout to bank:**

```python
# Tasker requests payout to bank
payout = handler.create_payout(
    account_id="acct_xxx",
    amount=45000,  # All available balance
    description="TaskUp earnings"
)

# Returns:
{
    "payout_id": "po_xxx",
    "status": "in_transit",
    "arrival_date": 1234567890  # Unix timestamp
}
```

**What Happens:**
- ✅ 450 NOK → Tasker's bank account
- ✅ Webhook `payout.paid` fires (or `payout.failed`)
- ✅ Money arrives in 1-3 business days

---

## 🎯 PLATFORM FEE CALCULATION

**Setting:** `PLATFORM_FEE_PERCENTAGE=10` (10%)

**Example:**
```
Task Budget: 500 NOK
Platform Fee: 500 × 0.10 = 50 NOK
Tasker Gets: 500 - 50 = 450 NOK
```

**In code:**
```python
original_amount = 50000  # 500 NOK in øre
platform_fee = int(original_amount * 0.10)  # 5000 øre = 50 NOK
tasker_amount = original_amount - platform_fee  # 45000 øre = 450 NOK
```

**The fee is automatically calculated and applied in `transfer_to_tasker()`**

---

## 📡 WEBHOOK EVENTS HANDLED

All configured in Stripe Dashboard → Webhooks:

### **Customer Payments:**
✅ `payment_intent.succeeded` - Customer payment successful  
✅ `payment_intent.payment_failed` - Payment failed  
✅ `payment_intent.canceled` - Payment canceled  
✅ `charge.succeeded` - Charge successful (backup)  
✅ `charge.refunded` - Refund issued  

### **Stripe Connect:**
✅ `account.updated` - Tasker account status changed  
✅ `payout.paid` - Payout to tasker's bank succeeded  
✅ `payout.failed` - Payout failed  
✅ `transfer.created` - Transfer to tasker created  
✅ `transfer.paid` - Transfer successful  

### **Optional:**
✅ `checkout.session.completed` - If using Stripe Checkout

---

## 🔧 SETUP STEPS

### **1. Verify Webhook in Stripe Dashboard**

1. Go to: https://dashboard.stripe.com/webhooks
2. Check webhook exists:
   - URL: `https://taskup.no/api/webhooks/stripe`
   - Status: ✅ Enabled
3. Verify events selected (see list above)
4. Signing secret matches: `whsec_hBD86NUODuC72Z90pjpLvSWW585bVvIE`

### **2. Add Credentials to .env**

```bash
# Copy production config
cp .env.taskup.production .env

# Verify Stripe credentials are correct
cat .env | grep STRIPE
```

### **3. Test Webhook Locally (Development)**

```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe

# Login to Stripe
stripe login

# Forward webhooks to local server
stripe listen --forward-to localhost:8000/api/webhooks/stripe

# In another terminal, start your server
python backend/main.py

# Trigger test events
stripe trigger payment_intent.succeeded
stripe trigger account.updated
stripe trigger transfer.created
```

### **4. Test Complete Flow**

**A. Customer Payment:**
```bash
# Use Stripe test cards
# Success: 4242 4242 4242 4242
# Decline: 4000 0000 0000 0002

# Check webhook logs in Stripe Dashboard
# Verify database updated
```

**B. Tasker Onboarding:**
```bash
# Create Connect account
curl -X POST http://localhost:8000/api/payments/connect/onboard \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"email": "tasker@test.com"}'

# Visit onboarding URL
# Use test business: Use test data button in Connect onboarding

# Check webhook: account.updated
```

**C. Transfer & Payout:**
```bash
# After task completion
curl -X POST http://localhost:8000/api/admin/payments/TRANSACTION_ID/release \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -d '{"reason": "Task completed"}'

# Check webhooks:
# - transfer.created
# - transfer.paid

# Verify tasker balance increased
```

---

## 📊 MONITORING

### **Stripe Dashboard:**
- **Payments:** https://dashboard.stripe.com/payments
- **Connect:** https://dashboard.stripe.com/connect/accounts/overview
- **Webhooks:** https://dashboard.stripe.com/webhooks
- **Logs:** https://dashboard.stripe.com/logs

### **Watch for:**
- ✅ Payment success rate > 95%
- ✅ Connect onboarding completion rate
- ✅ Transfer success rate > 99%
- ✅ Payout success rate > 99%
- ⚠️ Failed webhooks (retry automatically)
- ❌ Disputes (handle quickly)

---

## 🚨 ERROR HANDLING

### **Payment Failed:**
```python
# Webhook: payment_intent.payment_failed
# Action:
# 1. Log error message
# 2. Notify customer
# 3. Suggest retry or alternative payment
```

### **Transfer Failed:**
```python
# Rare, but possible if:
# - Tasker account disabled
# - Insufficient balance (shouldn't happen)
# 
# Action:
# 1. Alert admin
# 2. Hold money in TaskUp account
# 3. Manual resolution
```

### **Payout Failed:**
```python
# Webhook: payout.failed
# Common reasons:
# - Invalid bank account
# - Insufficient balance
# - Account restricted
#
# Action:
# 1. Notify tasker
# 2. Ask to update bank details
# 3. Retry payout
```

---

## 💰 REFUNDS

### **Full Refund:**
```python
refund = handler.create_refund(
    payment_intent_id="pi_xxx",
    reason="requested_by_customer"
)
# Money goes back to customer
# Transfer NOT created to tasker
```

### **Partial Refund:**
```python
refund = handler.create_refund(
    payment_intent_id="pi_xxx",
    amount=25000,  # 250 NOK out of 500 NOK
    reason="partial_work_completed"
)
# Transfer partial amount to tasker
```

### **After Transfer:**
```python
# If already transferred to tasker, need to reverse
reversal = handler.reverse_transfer(
    transfer_id="tr_xxx",
    reason="Task cancelled"
)
# Takes money back from tasker's balance
# Then refund customer
```

---

## ✅ CHECKLIST

### **Before Launch:**
- [x] Stripe credentials added to .env
- [x] Webhook URL configured in Stripe
- [x] Webhook signing secret verified
- [ ] Test customer payment end-to-end
- [ ] Test tasker onboarding
- [ ] Test transfer after completion
- [ ] Test refund flow
- [ ] Test webhook delivery
- [ ] Monitor Stripe logs for errors

### **After Launch:**
- [ ] Monitor payment success rate
- [ ] Monitor Connect onboarding rate
- [ ] Monitor transfer/payout success
- [ ] Set up alerts for failures
- [ ] Regular reconciliation (Stripe vs database)

---

## 🎉 YOU'RE READY!

**Your Stripe integration is configured and ready to handle:**
- ✅ Customer payments (Payment Intents)
- ✅ Escrow holding (in TaskUp's account)
- ✅ Tasker onboarding (Stripe Connect Express)
- ✅ Payouts after completion (Transfers)
- ✅ Platform fees (10% automatic)
- ✅ Webhooks (all events)
- ✅ Refunds (full & partial)

**Files created:**
1. `backend/payments/stripe_handler_complete.py` - All Stripe logic
2. `backend/payments/stripe_webhooks_complete.py` - All webhook handlers
3. `.env.taskup.production` - Your credentials

**Next:** Test the complete flow! 🚀
