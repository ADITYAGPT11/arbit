import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../App";
import { TrendingUp, ArrowLeftRight, Shield, BarChart3 } from "lucide-react";

export default function Login() {
  const { user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (user) {
      navigate("/dashboard", { replace: true });
    }
  }, [user, navigate]);

  const handleLogin = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + "/dashboard";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  const features = [
    {
      icon: ArrowLeftRight,
      title: "Cross-Exchange Arbitrage",
      description: "Detect NSE vs BSE price differences in real-time",
    },
    {
      icon: TrendingUp,
      title: "F&O Analytics",
      description: "Cash & Carry, Synthetic Futures, Calendar Spreads",
    },
    {
      icon: Shield,
      title: "Risk Management",
      description: "Position sizing, VaR, and margin calculations",
    },
    {
      icon: BarChart3,
      title: "Performance Analytics",
      description: "Sharpe, Sortino, Drawdown analysis",
    },
  ];

  return (
    <div className="min-h-screen bg-[#0a0a0a] flex" data-testid="login-page">
      {/* Left Panel - Branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-blue-900/20 to-purple-900/20 p-12 flex-col justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">
            ARBIT<span className="text-blue-500">PRO</span>
          </h1>
          <p className="text-zinc-400">Indian Markets Arbitrage Platform</p>
        </div>

        <div className="space-y-6">
          {features.map((feature, idx) => (
            <div key={idx} className="flex items-start gap-4">
              <div className="p-2 bg-blue-500/10 rounded-lg">
                <feature.icon className="w-6 h-6 text-blue-500" />
              </div>
              <div>
                <h3 className="font-semibold text-white">{feature.title}</h3>
                <p className="text-sm text-zinc-400">{feature.description}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="text-zinc-500 text-sm">
          <p>Supported Exchanges: NSE • BSE • MCX</p>
          <p>Indices: NIFTY • BANKNIFTY • FINNIFTY • SENSEX • BANKEX</p>
        </div>
      </div>

      {/* Right Panel - Login */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          <div className="text-center mb-8">
            <h2 className="text-2xl font-bold text-white mb-2">Welcome Back</h2>
            <p className="text-zinc-400">
              Sign in to access your trading dashboard
            </p>
          </div>

          <div className="card p-8">
            <button
              onClick={handleLogin}
              className="w-full flex items-center justify-center gap-3 bg-white text-gray-900 font-medium py-3 px-4 rounded-lg hover:bg-gray-100 transition-colors"
              data-testid="google-login-btn"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24">
                <path
                  fill="currentColor"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="currentColor"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="currentColor"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                />
                <path
                  fill="currentColor"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                />
              </svg>
              Continue with Google
            </button>

            <div className="mt-6 text-center text-sm text-zinc-500">
              <p>By signing in, you agree to our</p>
              <p>
                <a href="#" className="text-blue-500 hover:underline">
                  Terms of Service
                </a>{" "}
                and{" "}
                <a href="#" className="text-blue-500 hover:underline">
                  Privacy Policy
                </a>
              </p>
            </div>
          </div>

          <div className="mt-8 text-center text-xs text-zinc-600">
            <p>For professional traders and institutions</p>
            <p>Real-time market data • Sub-100ms detection</p>
          </div>
        </div>
      </div>
    </div>
  );
}
