import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CreditCard, Smartphone, Shield, AlertCircle, Loader, Check } from 'lucide-react';
import { v4 as uuidv4 } from 'uuid';

interface PaymentFlowProps {
  taskId: string;
  taskTitle: string;
  amount: number; // in NOK (e.g. 500 for 500 kr)
  onSuccess?: () => void;
  onError?: (error: string) => void;
}

type PaymentMethod = 'vipps' | 'stripe';
type PaymentStep = 'select' | 'processing' | 'success' | 'error';

export default function PaymentFlow({ 
  taskId, 
  taskTitle, 
  amount, 
  onSuccess, 
  onError 
}: PaymentFlowProps) {
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('vipps');
  const [step, setStep] = useState<PaymentStep>('select');
  const [error, setError] = useState<string>('');
  const [phoneNumber, setPhoneNumber] = useState<string>('');
  const navigate = useNavigate();

  const handlePayment = async () => {
    setStep('processing');
    setError('');

    try {
      // Generate idempotency key
      const idempotencyKey = uuidv4();

      // Get auth token
      const token = localStorage.getItem('token');
      if (!token) {
        throw new Error('Not authenticated');
      }

      // Call payment API
      const response = await fetch('/api/payments/add-funds', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
          'X-Idempotency-Key': idempotencyKey
        },
        body: JSON.stringify({
          amount: amount,
          payment_method: paymentMethod,
          phone_number: paymentMethod === 'vipps' ? phoneNumber : undefined,
          metadata: {
            task_id: taskId,
            task_title: taskTitle
          }
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || 'Payment failed');
      }

      const data = await response.json();

      if (paymentMethod === 'vipps') {
        // Redirect to Vipps
        if (data.payment_url) {
          window.location.href = data.payment_url;
        } else {
          throw new Error('No payment URL received');
        }
      } else if (paymentMethod === 'stripe') {
        // Redirect to Stripe Checkout (or use Elements)
        if (data.client_secret) {
          // For now, we'll use Stripe's hosted page
          // You can integrate Stripe Elements here for embedded payment
          const stripePaymentUrl = `https://checkout.stripe.com/pay/${data.client_secret}`;
          window.location.href = stripePaymentUrl;
        } else {
          throw new Error('No client secret received');
        }
      }

      // Note: Payment success will be handled by webhook
      // User will be redirected back to app after payment

    } catch (err: any) {
      console.error('Payment error:', err);
      setError(err.message || 'Payment failed. Please try again.');
      setStep('error');
      
      if (onError) {
        onError(err.message);
      }
    }
  };

  const validatePhoneNumber = (phone: string): boolean => {
    // Norwegian phone number validation
    const phoneRegex = /^(\+47|0047|47)?[4-9]\d{7}$/;
    return phoneRegex.test(phone.replace(/\s/g, ''));
  };

  const canProceed = () => {
    if (paymentMethod === 'vipps') {
      return phoneNumber && validatePhoneNumber(phoneNumber);
    }
    return true; // Stripe doesn't need phone number
  };

  return (
    <div className="max-w-2xl mx-auto p-6">
      {/* Header */}
      <div className="mb-8">
        <h2 className="text-3xl font-bold text-white mb-2">
          Add Funds to Wallet
        </h2>
        <p className="text-gray-400">
          Secure payment with escrow protection
        </p>
      </div>

      {/* Amount Display */}
      <div className="bg-gradient-to-br from-cyan-600 to-blue-600 rounded-xl p-6 mb-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-cyan-100 text-sm mb-1">Amount to pay</p>
            <p className="text-white text-4xl font-bold">
              {new Intl.NumberFormat('nb-NO', {
                style: 'currency',
                currency: 'NOK',
                minimumFractionDigits: 0
              }).format(amount)}
            </p>
          </div>
          <div className="w-16 h-16 bg-white/20 rounded-full flex items-center justify-center">
            <Shield className="w-8 h-8 text-white" />
          </div>
        </div>
        <p className="text-cyan-100 text-sm mt-4">
          For: {taskTitle}
        </p>
      </div>

      {/* Payment Method Selection */}
      {step === 'select' && (
        <div className="space-y-4 mb-6">
          <h3 className="text-lg font-semibold text-white mb-4">
            Choose Payment Method
          </h3>

          {/* Vipps Option */}
          <button
            onClick={() => setPaymentMethod('vipps')}
            className={`w-full p-6 rounded-xl border-2 transition-all text-left ${
              paymentMethod === 'vipps'
                ? 'border-orange-500 bg-orange-500/10'
                : 'border-gray-800 bg-gray-900 hover:border-gray-700'
            }`}
          >
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 bg-orange-500 rounded-lg flex items-center justify-center flex-shrink-0">
                <Smartphone className="w-6 h-6 text-white" />
              </div>
              <div className="flex-1">
                <h4 className="text-white font-semibold mb-1">Vipps</h4>
                <p className="text-gray-400 text-sm mb-3">
                  Fast and secure payment with Vipps
                </p>
                {paymentMethod === 'vipps' && (
                  <input
                    type="tel"
                    placeholder="Phone number (e.g., 98765432)"
                    value={phoneNumber}
                    onChange={(e) => setPhoneNumber(e.target.value)}
                    className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-orange-500"
                  />
                )}
              </div>
              {paymentMethod === 'vipps' && (
                <Check className="w-6 h-6 text-orange-500" />
              )}
            </div>
          </button>

          {/* Stripe Option */}
          <button
            onClick={() => setPaymentMethod('stripe')}
            className={`w-full p-6 rounded-xl border-2 transition-all text-left ${
              paymentMethod === 'stripe'
                ? 'border-purple-500 bg-purple-500/10'
                : 'border-gray-800 bg-gray-900 hover:border-gray-700'
            }`}
          >
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 bg-purple-500 rounded-lg flex items-center justify-center flex-shrink-0">
                <CreditCard className="w-6 h-6 text-white" />
              </div>
              <div className="flex-1">
                <h4 className="text-white font-semibold mb-1">Card Payment</h4>
                <p className="text-gray-400 text-sm">
                  Pay with credit or debit card via Stripe
                </p>
              </div>
              {paymentMethod === 'stripe' && (
                <Check className="w-6 h-6 text-purple-500" />
              )}
            </div>
          </button>
        </div>
      )}

      {/* Processing State */}
      {step === 'processing' && (
        <div className="text-center py-12">
          <Loader className="w-12 h-12 text-cyan-500 animate-spin mx-auto mb-4" />
          <p className="text-white font-medium">Processing payment...</p>
          <p className="text-gray-400 text-sm mt-2">Please wait</p>
        </div>
      )}

      {/* Error State */}
      {step === 'error' && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 mb-6">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-6 h-6 text-red-500 flex-shrink-0 mt-0.5" />
            <div>
              <h4 className="text-red-500 font-semibold mb-1">Payment Failed</h4>
              <p className="text-red-300 text-sm">{error}</p>
            </div>
          </div>
          <button
            onClick={() => setStep('select')}
            className="mt-4 w-full py-3 bg-gray-800 hover:bg-gray-700 text-white font-medium rounded-lg transition-colors"
          >
            Try Again
          </button>
        </div>
      )}

      {/* Security Info */}
      {step === 'select' && (
        <>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
            <div className="flex items-start gap-3 mb-4">
              <Shield className="w-5 h-5 text-cyan-500 flex-shrink-0 mt-0.5" />
              <div>
                <h4 className="text-white font-semibold mb-1">Escrow Protection</h4>
                <p className="text-gray-400 text-sm">
                  Your payment is held securely in escrow until the task is completed. 
                  Money is only released when you confirm the work is done.
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <Check className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
              <div>
                <h4 className="text-white font-semibold mb-1">Full Refund Protection</h4>
                <p className="text-gray-400 text-sm">
                  If the tasker doesn't deliver, you get your money back. No questions asked.
                </p>
              </div>
            </div>
          </div>

          {/* Pay Button */}
          <button
            onClick={handlePayment}
            disabled={!canProceed()}
            className={`w-full py-4 font-semibold rounded-lg transition-all ${
              canProceed()
                ? 'bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-700 hover:to-blue-700 text-white shadow-lg hover:shadow-cyan-500/50'
                : 'bg-gray-800 text-gray-500 cursor-not-allowed'
            }`}
          >
            {paymentMethod === 'vipps' ? 'Pay with Vipps' : 'Pay with Card'}
          </button>

          {/* Cancel Button */}
          <button
            onClick={() => navigate(-1)}
            className="w-full mt-3 py-3 bg-gray-800 hover:bg-gray-700 text-white font-medium rounded-lg transition-colors"
          >
            Cancel
          </button>
        </>
      )}

      {/* Terms */}
      <p className="text-gray-500 text-xs text-center mt-6">
        By continuing, you agree to our{' '}
        <a href="/legal/terms" className="text-cyan-500 hover:underline">
          Terms of Service
        </a>{' '}
        and{' '}
        <a href="/legal/privacy" className="text-cyan-500 hover:underline">
          Privacy Policy
        </a>
      </p>
    </div>
  );
}

// ============================================
// USAGE EXAMPLE
// ============================================

/*
import PaymentFlow from '@/components/PaymentFlow';

function TaskPaymentPage() {
  const { taskId } = useParams();
  const [task, setTask] = useState(null);

  useEffect(() => {
    // Load task details
    loadTask();
  }, [taskId]);

  const handlePaymentSuccess = () => {
    // Redirect to task page or show success message
    navigate(`/tasks/${taskId}`);
  };

  const handlePaymentError = (error: string) => {
    console.error('Payment error:', error);
  };

  if (!task) return <div>Loading...</div>;

  return (
    <PaymentFlow
      taskId={task.id}
      taskTitle={task.title}
      amount={task.budget / 100} // Convert cents to NOK
      onSuccess={handlePaymentSuccess}
      onError={handlePaymentError}
    />
  );
}
*/

// ============================================
// PAYMENT STATUS CHECKER
// ============================================

export function usePaymentStatus(orderId: string) {
  const [status, setStatus] = useState<string>('initiated');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!orderId) return;

    const checkStatus = async () => {
      try {
        const token = localStorage.getItem('token');
        const response = await fetch(`/api/payments/status/${orderId}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });

        if (response.ok) {
          const data = await response.json();
          setStatus(data.status);
        }
      } catch (error) {
        console.error('Failed to check payment status:', error);
      } finally {
        setLoading(false);
      }
    };

    checkStatus();
    
    // Poll every 3 seconds while pending
    const interval = setInterval(() => {
      if (status === 'initiated' || status === 'processing') {
        checkStatus();
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [orderId, status]);

  return { status, loading };
}
