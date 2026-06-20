import { useEffect, useState, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import { useAuth, API } from "../App";
import {
  CheckCircle2,
  XCircle,
  Plug,
  RefreshCw,
  ExternalLink,
  Loader2,
  ShieldCheck,
  Clock,
  Sparkles,
  AlertTriangle,
  LogIn,
} from "lucide-react";

const BROKER_TAGLINE = {
  angel_one: "India's largest retail broker — connect via Angel One SmartAPI Publisher Login",
  zerodha: "Connect Kite via OAuth (coming soon)",
  upstox: "Connect Upstox via OAuth 2.0 (coming soon)",
  fyers: "Connect Fyers via OAuth 2.0 (coming soon)",
  icici_direct: "Connect ICICI Direct via Breeze Connect (coming soon)",
};

const BROKER_GRADIENT = {
  angel_one: "from-orange-500/20 to-red-600/10 border-orange-500/30",
  zerodha: "from-blue-500/10 to-cyan-600/5 border-blue-500/20",
  upstox: "from-purple-500/10 to-pink-600/5 border-purple-500/20",
  fyers: "from-emerald-500/10 to-teal-600/5 border-emerald-500/20",
  icici_direct: "from-amber-500/10 to-orange-600/5 border-amber-500/20",
};

function formatRemaining(expiresAt) {
  if (!expiresAt) return null;
  const ms = new Date(expiresAt).getTime() - Date.now();
  if (ms <= 0) return "Expired";
  const h = Math.floor(ms / 3600000);
  const m = Math.floor((ms % 3600000) / 60000);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

export default function ConnectBroker() {
  const { user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const [brokers, setBrokers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [connectingId, setConnectingId] = useState(null);

  const fetchBrokers = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/brokers/list`, { withCredentials: true });
      setBrokers(res.data.brokers || []);
    } catch (err) {
      toast.error("Failed to load brokers");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBrokers();
  }, [fetchBrokers]);

  // Handle callback redirect (success / error from broker)
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const status = params.get("status");
    const broker = params.get("broker");
    const message = params.get("message");
    if (!status) return;
    if (status === "success") {
      toast.success(`${broker || "Broker"} connected successfully`);
    } else {
      toast.error(message || "Broker connection failed");
    }
    // Clean URL & refresh status
    navigate("/connect-broker", { replace: true });
    fetchBrokers();
  }, [location.search, navigate, fetchBrokers]);

  const handleConnect = async (broker) => {
    if (!user) {
      toast.info("Please login first to connect a broker");
      return;
    }
    if (broker.coming_soon) {
      toast.info(`${broker.display_name} integration is coming soon`);
      return;
    }
    if (!broker.platform_configured) {
      toast.error(
        `${broker.display_name} is not yet configured on this server. Ask the admin to set the platform API key.`
      );
      return;
    }
    try {
      setConnectingId(broker.broker_id);
      const res = await axios.post(
        `${API}/brokers/${broker.broker_id}/connect`,
        {},
        { withCredentials: true }
      );
      const { login_url } = res.data;
      if (!login_url) throw new Error("No login URL returned");
      // Redirect in same tab — broker will redirect back to /connect-broker via our /api callback.
      window.location.href = login_url;
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || "Connect failed";
      toast.error(msg);
      setConnectingId(null);
    }
  };

  const handleDisconnect = async (broker) => {
    if (!window.confirm(`Disconnect ${broker.display_name}?`)) return;
    try {
      await axios.post(
        `${API}/brokers/${broker.broker_id}/disconnect`,
        {},
        { withCredentials: true }
      );
      toast.success(`Disconnected from ${broker.display_name}`);
      fetchBrokers();
    } catch (err) {
      const msg = err.response?.data?.detail || "Disconnect failed";
      toast.error(msg);
    }
  };

  return (
    <div className="p-4 md:p-8 max-w-6xl mx-auto" data-testid="connect-broker-page">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500/20 to-purple-500/20 flex items-center justify-center border border-blue-500/30">
            <Plug className="w-5 h-5 text-blue-400" />
          </div>
          <h1 className="text-2xl md:text-3xl font-bold text-white">Connect Broker</h1>
        </div>
        <p className="text-zinc-400 text-sm max-w-2xl">
          Connect your trading account to enable live market data and order placement.
          We <span className="text-emerald-400 font-medium">never store</span> your MPIN,
          TOTP, or password — you log in directly on your broker's site.
        </p>
      </div>

      {/* Login prompt */}
      {!user && (
        <div className="mb-6 p-4 rounded-xl border border-amber-500/30 bg-amber-500/5 flex items-center gap-3" data-testid="login-prompt">
          <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0" />
          <div className="flex-1">
            <div className="text-amber-200 font-medium text-sm">Login required</div>
            <div className="text-zinc-400 text-xs">
              Sign in with Google to connect your broker account.
            </div>
          </div>
          <button
            onClick={() => {
              const redirectUrl = window.location.origin + "/connect-broker";
              window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
            }}
            className="btn btn-primary text-xs flex items-center gap-2"
          >
            <LogIn className="w-3 h-3" /> Login
          </button>
        </div>
      )}

      {/* Security note */}
      <div className="mb-8 p-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5">
        <div className="flex items-start gap-3">
          <ShieldCheck className="w-5 h-5 text-emerald-400 flex-shrink-0 mt-0.5" />
          <div className="text-xs text-zinc-300 leading-relaxed">
            <div className="font-medium text-emerald-300 mb-1">How it works</div>
            You click <span className="text-white">Connect</span> → you're redirected to your
            broker's official login page → you enter your credentials there → the broker
            sends a short-lived authorization token back to ARBIT. Tokens live in server
            memory only and auto-expire in ~12 hours.
          </div>
        </div>
      </div>

      {/* Brokers */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-6 h-6 text-zinc-400 animate-spin" />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {brokers.map((b) => {
            const gradient = BROKER_GRADIENT[b.broker_id] || "from-zinc-800/40 to-zinc-900/40 border-zinc-700/40";
            const isConnecting = connectingId === b.broker_id;
            const remaining = formatRemaining(b.expires_at);
            return (
              <div
                key={b.broker_id}
                className={`relative rounded-xl border bg-gradient-to-br ${gradient} p-5 transition-all hover:scale-[1.01]`}
                data-testid={`broker-card-${b.broker_id}`}
              >
                {/* Coming soon ribbon */}
                {b.coming_soon && (
                  <div className="absolute top-3 right-3 px-2 py-0.5 rounded-full bg-zinc-800/80 border border-zinc-700 text-[10px] font-semibold uppercase tracking-wider text-zinc-300 flex items-center gap-1">
                    <Sparkles className="w-3 h-3" />
                    Coming soon
                  </div>
                )}

                {/* Header */}
                <div className="flex items-start gap-3 mb-4">
                  <div className="w-12 h-12 rounded-lg bg-zinc-950/60 border border-zinc-700/50 flex items-center justify-center text-white font-bold text-lg uppercase">
                    {b.display_name.charAt(0)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="text-lg font-semibold text-white">{b.display_name}</h3>
                      {b.is_connected && (
                        <span className="px-2 py-0.5 rounded-full bg-emerald-500/15 border border-emerald-500/40 text-[10px] font-semibold text-emerald-300 flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" />
                          Connected
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-zinc-400 mt-0.5">
                      {BROKER_TAGLINE[b.broker_id] || "OAuth-based broker connection"}
                    </p>
                  </div>
                </div>

                {/* Connected info */}
                {b.is_connected && b.profile && (
                  <div className="mb-4 p-3 rounded-lg bg-black/30 border border-zinc-800 text-xs space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-zinc-500">Client ID</span>
                      <span className="text-zinc-200 font-mono">{b.profile.client_id || "—"}</span>
                    </div>
                    {b.profile.name && (
                      <div className="flex items-center justify-between">
                        <span className="text-zinc-500">Name</span>
                        <span className="text-zinc-200">{b.profile.name}</span>
                      </div>
                    )}
                    {remaining && (
                      <div className="flex items-center justify-between">
                        <span className="text-zinc-500 flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          Expires in
                        </span>
                        <span className="text-zinc-200">{remaining}</span>
                      </div>
                    )}
                  </div>
                )}

                {/* Platform-not-configured warning */}
                {!b.coming_soon && !b.platform_configured && (
                  <div className="mb-4 p-2 rounded-lg bg-amber-500/5 border border-amber-500/20 text-[11px] text-amber-200 flex items-start gap-2">
                    <AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                    <span>
                      Not configured on this server yet. ARBIT admin must set the platform
                      API key in backend environment.
                    </span>
                  </div>
                )}

                {/* Actions */}
                <div className="flex items-center gap-2">
                  {b.is_connected ? (
                    <>
                      <button
                        onClick={() => handleDisconnect(b)}
                        className="btn btn-secondary text-xs flex-1 flex items-center justify-center gap-1.5"
                        data-testid={`disconnect-${b.broker_id}`}
                      >
                        <XCircle className="w-3.5 h-3.5" />
                        Disconnect
                      </button>
                      <button
                        onClick={() => handleConnect(b)}
                        disabled={isConnecting}
                        className="btn btn-secondary text-xs px-3 flex items-center justify-center gap-1.5"
                        data-testid={`reconnect-${b.broker_id}`}
                        title="Reconnect"
                      >
                        <RefreshCw className={`w-3.5 h-3.5 ${isConnecting ? "animate-spin" : ""}`} />
                      </button>
                    </>
                  ) : (
                    <button
                      onClick={() => handleConnect(b)}
                      disabled={b.coming_soon || isConnecting || !user}
                      className={`btn text-xs flex-1 flex items-center justify-center gap-1.5 ${
                        b.coming_soon || !user ? "btn-secondary opacity-60 cursor-not-allowed" : "btn-primary"
                      }`}
                      data-testid={`connect-${b.broker_id}`}
                    >
                      {isConnecting ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          Redirecting...
                        </>
                      ) : (
                        <>
                          <Plug className="w-3.5 h-3.5" />
                          {b.coming_soon ? "Coming soon" : "Connect"}
                        </>
                      )}
                    </button>
                  )}
                  {b.website && (
                    <a
                      href={b.website}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn btn-secondary text-xs px-3 flex items-center justify-center"
                      title={`Visit ${b.display_name}`}
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Footer info */}
      <div className="mt-10 text-center text-xs text-zinc-600">
        More brokers coming soon — Zerodha, Upstox, Fyers, ICICI Direct.
        <br />
        Suggest a broker: <a href="mailto:support@arbitpro.in" className="text-blue-400 hover:underline">support@arbitpro.in</a>
      </div>
    </div>
  );
}
