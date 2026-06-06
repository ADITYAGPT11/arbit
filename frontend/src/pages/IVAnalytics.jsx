import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import { API } from "../App";
import {
  RefreshCw,
  Zap,
  TrendingUp,
  TrendingDown,
  Target,
  AlertTriangle,
  ThumbsUp,
  ThumbsDown,
  Minus,
  Clock,
} from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  ReferenceLine, BarChart, Bar, CartesianGrid, Cell,
} from "recharts";
import { toast } from "sonner";

const REFRESH_INTERVAL = 10000; // 10s

export default function IVAnalytics() {
  const [underlying, setUnderlying] = useState("NIFTY");
  const [data, setData] = useState(null);
  const [underlyings, setUnderlyings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);
  const intervalRef = useRef(null);

  useEffect(() => {
    axios.get(`${API}/options/underlyings`).then((r) => setUnderlyings(r.data)).catch(() => {});
  }, []);

  const fetchData = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/iv/dashboard?underlying=${underlying}&num_strikes=20`, { timeout: 45000 });
      setData(res.data);
      setLastUpdate(new Date());
    } catch (err) {
      console.error("IV fetch error:", err);
      if (!data) toast.error("Failed to fetch IV data");
    } finally {
      setLoading(false);
    }
  }, [underlying]);

  useEffect(() => {
    setLoading(true);
    setData(null);
    fetchData();
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (autoRefresh) {
      intervalRef.current = setInterval(fetchData, REFRESH_INTERVAL);
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [fetchData, autoRefresh]);

  const SignalIcon = ({ signal }) => {
    if (signal === "SELL_PREMIUM") return <ThumbsUp className="w-5 h-5 text-green-500" />;
    if (signal === "AVOID_SELLING") return <ThumbsDown className="w-5 h-5 text-red-500" />;
    return <Minus className="w-5 h-5 text-zinc-400" />;
  };

  const signalColor = (signal) => {
    if (signal === "SELL_PREMIUM") return "text-green-500";
    if (signal === "AVOID_SELLING") return "text-red-500";
    return "text-zinc-400";
  };

  const signalBg = (signal) => {
    if (signal === "SELL_PREMIUM") return "bg-green-900/20 border-green-900/50";
    if (signal === "AVOID_SELLING") return "bg-red-900/20 border-red-900/50";
    return "bg-zinc-900 border-zinc-800";
  };

  if (loading && !data) {
    return (
      <div className="page-container">
        <div className="flex flex-col items-center justify-center min-h-[400px]">
          <div className="loading-spinner mb-4"></div>
          <p className="text-zinc-400">Computing IV analytics...</p>
          <p className="text-xs text-zinc-500 mt-2">Calculating Black-Scholes IV for each strike</p>
        </div>
      </div>
    );
  }

  const signal = data?.seller_signal;
  const maxPain = data?.max_pain;

  // Prepare skew chart data
  const skewData = (data?.iv_skew || []).map((s) => ({
    strike: s.strike,
    moneyness: s.moneyness,
    ce_iv: s.ce_iv || 0,
    pe_iv: s.pe_iv || 0,
    label: s.strike === data?.atm_strike ? "ATM" : "",
  }));

  // Prepare max pain chart data (top 15 around max pain)
  const painData = (() => {
    if (!maxPain?.pain_distribution) return [];
    const all = maxPain.pain_distribution;
    const mpIdx = all.findIndex((p) => p.strike === maxPain.max_pain_strike);
    const start = Math.max(0, mpIdx - 7);
    const end = Math.min(all.length, mpIdx + 8);
    return all.slice(start, end).map((p) => ({
      strike: p.strike,
      pain: Math.round(p.total_pain / 100000), // In Lakhs
      isMaxPain: p.strike === maxPain.max_pain_strike,
    }));
  })();

  return (
    <div className="page-container" data-testid="iv-analytics-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-3 mb-5">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold">IV Analytics</h1>
          <p className="text-zinc-500 text-xs sm:text-sm">Options Seller's Dashboard — IV Expansion & Crush Detection</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={underlying}
            onChange={(e) => setUnderlying(e.target.value)}
            className="oc-select"
            data-testid="iv-underlying-select"
          >
            {underlyings.filter((u) => u.is_index).map((u) => (
              <option key={u.name} value={u.name}>{u.name}</option>
            ))}
            {underlyings.filter((u) => !u.is_index).slice(0, 20).map((u) => (
              <option key={u.name} value={u.name}>{u.name}</option>
            ))}
          </select>
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-[11px] sm:text-xs font-medium ${
              autoRefresh ? "bg-green-900/20 border-green-900/50 text-green-500" : "bg-zinc-900 border-zinc-800 text-zinc-400"
            }`}
            data-testid="iv-auto-refresh"
          >
            <Zap className="w-3 h-3" />{autoRefresh ? "Auto 10s" : "Paused"}
          </button>
          <button onClick={fetchData} className="btn btn-secondary flex items-center gap-1 text-xs px-3 py-1.5" data-testid="iv-refresh-btn">
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {data && (
        <>
          {/* Seller Signal Banner */}
          <div className={`p-4 rounded-lg border mb-5 ${signalBg(signal?.signal)}`} data-testid="seller-signal">
            <div className="flex items-center gap-3">
              <SignalIcon signal={signal?.signal} />
              <div>
                <div className={`text-base sm:text-lg font-bold ${signalColor(signal?.signal)}`}>
                  {signal?.signal === "SELL_PREMIUM" ? "Sell Premium — IV is Rich" :
                   signal?.signal === "AVOID_SELLING" ? "Avoid Selling — IV is Cheap" :
                   "Neutral — Wait for Setup"}
                </div>
                {signal?.reasoning?.length > 0 && (
                  <div className="mt-1 space-y-0.5">
                    {signal.reasoning.map((r, i) => (
                      <p key={i} className="text-xs text-zinc-400">{r}</p>
                    ))}
                  </div>
                )}
                {data.iv_history_count < 10 && (
                  <p className="text-[10px] text-yellow-500 mt-1">
                    Building IV history... ({data.iv_history_count}/252 days). Signal accuracy improves with more data.
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Key Metrics */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-5">
            <div className="iv-metric-card" data-testid="atm-iv">
              <span className="iv-metric-label">ATM IV</span>
              <span className="iv-metric-value text-white">{data.atm_iv ? `${data.atm_iv}%` : "—"}</span>
            </div>
            <div className="iv-metric-card" data-testid="india-vix">
              <span className="iv-metric-label">India VIX</span>
              <span className="iv-metric-value text-yellow-400">{data.india_vix ? data.india_vix.toFixed(2) : "—"}</span>
            </div>
            <div className="iv-metric-card" data-testid="iv-rank">
              <span className="iv-metric-label">IV Rank</span>
              <span className={`iv-metric-value ${data.iv_rank != null ? (data.iv_rank >= 60 ? "text-green-400" : data.iv_rank <= 30 ? "text-red-400" : "text-zinc-300") : "text-zinc-500"}`}>
                {data.iv_rank != null ? `${data.iv_rank}%` : "Building..."}
              </span>
            </div>
            <div className="iv-metric-card" data-testid="iv-percentile">
              <span className="iv-metric-label">IV Percentile</span>
              <span className={`iv-metric-value ${data.iv_percentile != null ? (data.iv_percentile >= 60 ? "text-green-400" : data.iv_percentile <= 30 ? "text-red-400" : "text-zinc-300") : "text-zinc-500"}`}>
                {data.iv_percentile != null ? `${data.iv_percentile}%` : "Building..."}
              </span>
            </div>
            <div className="iv-metric-card" data-testid="hv">
              <span className="iv-metric-label">HV (20D)</span>
              <span className="iv-metric-value text-zinc-300">{data.historical_volatility ? `${data.historical_volatility}%` : "Building..."}</span>
            </div>
            <div className="iv-metric-card" data-testid="max-pain">
              <span className="iv-metric-label">Max Pain</span>
              <span className="iv-metric-value text-purple-400">
                {maxPain?.max_pain_strike?.toLocaleString("en-IN") || "—"}
              </span>
            </div>
          </div>

          {/* Context Row */}
          <div className="flex flex-wrap items-center gap-3 mb-5 text-xs text-zinc-500">
            <span>Spot: <span className="font-mono text-white font-medium">{data.spot_price?.toLocaleString("en-IN")}</span></span>
            <span>ATM: <span className="font-mono text-yellow-500">{data.atm_strike}</span></span>
            <span>Expiry: <span className="text-blue-400">{data.expiry}</span> ({data.days_to_expiry}d)</span>
            <span>PCR: <span className={`font-mono font-medium ${data.totals?.pcr > 1 ? "text-green-400" : "text-red-400"}`}>{data.totals?.pcr}</span></span>
            {lastUpdate && (
              <span className="flex items-center gap-1 text-zinc-600">
                <Clock className="w-3 h-3" />{lastUpdate.toLocaleTimeString()}
              </span>
            )}
          </div>

          {/* Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-5">
            {/* IV Skew Chart */}
            <div className="card" data-testid="iv-skew-chart">
              <div className="card-header">
                <span className="card-title">IV Smile / Skew</span>
                <span className="text-xs text-zinc-500">{data.underlying} {data.expiry}</span>
              </div>
              <div className="h-64">
                {skewData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={skewData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
                      <XAxis dataKey="strike" tick={{ fill: "#71717a", fontSize: 10 }} axisLine={false} tickLine={false}
                        tickFormatter={(v) => v >= 1000 ? `${(v/1000).toFixed(1)}K` : v} />
                      <YAxis tick={{ fill: "#71717a", fontSize: 10 }} axisLine={false} tickLine={false} domain={['auto', 'auto']}
                        tickFormatter={(v) => `${v}%`} />
                      <Tooltip contentStyle={{ background: "#1a1a1a", border: "1px solid #262626", borderRadius: "8px", fontSize: "12px" }}
                        labelFormatter={(v) => `Strike: ${v}`} formatter={(v, name) => [`${v}%`, name === "ce_iv" ? "Call IV" : "Put IV"]} />
                      {data.atm_strike && <ReferenceLine x={data.atm_strike} stroke="#eab308" strokeDasharray="5 5" label={{ value: "ATM", fill: "#eab308", fontSize: 10 }} />}
                      <Line type="monotone" dataKey="ce_iv" stroke="#22c55e" strokeWidth={2} dot={false} name="ce_iv" />
                      <Line type="monotone" dataKey="pe_iv" stroke="#ef4444" strokeWidth={2} dot={false} name="pe_iv" />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex items-center justify-center h-full text-zinc-500 text-sm">No IV data available</div>
                )}
              </div>
            </div>

            {/* Max Pain Chart */}
            <div className="card" data-testid="max-pain-chart">
              <div className="card-header">
                <span className="card-title">Max Pain Distribution</span>
                <div className="flex items-center gap-2">
                  <Target className="w-4 h-4 text-purple-400" />
                  <span className="text-xs text-purple-400 font-mono">{maxPain?.max_pain_strike?.toLocaleString("en-IN")}</span>
                </div>
              </div>
              <div className="h-64">
                {painData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={painData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
                      <XAxis dataKey="strike" tick={{ fill: "#71717a", fontSize: 9 }} axisLine={false} tickLine={false}
                        tickFormatter={(v) => v >= 1000 ? `${(v/1000).toFixed(1)}K` : v} />
                      <YAxis tick={{ fill: "#71717a", fontSize: 10 }} axisLine={false} tickLine={false}
                        tickFormatter={(v) => `${v}L`} />
                      <Tooltip contentStyle={{ background: "#1a1a1a", border: "1px solid #262626", borderRadius: "8px", fontSize: "12px" }}
                        labelFormatter={(v) => `Strike: ${v}`} formatter={(v) => [`₹${v}L`, "Total Pain"]} />
                      {maxPain?.max_pain_strike && <ReferenceLine x={maxPain.max_pain_strike} stroke="#a855f7" strokeDasharray="5 5" />}
                      <Bar dataKey="pain" radius={[3, 3, 0, 0]}>
                        {painData.map((entry, idx) => (
                          <Cell key={idx} fill={entry.isMaxPain ? "#a855f7" : "#3f3f46"} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex items-center justify-center h-full text-zinc-500 text-sm">No max pain data</div>
                )}
              </div>
            </div>
          </div>

          {/* IV Explanation for Options Sellers */}
          <div className="card" data-testid="iv-guide">
            <div className="card-header">
              <span className="card-title">Options Seller's Guide</span>
              <AlertTriangle className="w-4 h-4 text-yellow-500" />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
              <div className="p-3 bg-zinc-900/50 rounded-lg">
                <div className="font-semibold text-green-400 mb-1">IV Rank &gt; 60%</div>
                <p className="text-zinc-400">IV is elevated vs its yearly range. Premiums are expensive — favorable for selling.</p>
              </div>
              <div className="p-3 bg-zinc-900/50 rounded-lg">
                <div className="font-semibold text-red-400 mb-1">IV Rank &lt; 30%</div>
                <p className="text-zinc-400">IV is depressed. Premiums are cheap — avoid selling, or buy for IV expansion.</p>
              </div>
              <div className="p-3 bg-zinc-900/50 rounded-lg">
                <div className="font-semibold text-yellow-400 mb-1">IV &gt; HV</div>
                <p className="text-zinc-400">Implied vol exceeds realized vol — market is pricing in more move than is actually happening. Overpriced options.</p>
              </div>
              <div className="p-3 bg-zinc-900/50 rounded-lg">
                <div className="font-semibold text-purple-400 mb-1">Max Pain</div>
                <p className="text-zinc-400">Strike where option buyers lose the most. Price tends to gravitate here at expiry — useful for strike selection.</p>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
