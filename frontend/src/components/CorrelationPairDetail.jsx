import { useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  AreaChart,
  Area,
  BarChart,
  Bar,
} from "recharts";
import {
  X,
  TrendingUp,
  TrendingDown,
  Activity,
  HelpCircle,
  FlaskConical,
  Play,
  Settings2,
} from "lucide-react";
import axios from "axios";
import { API } from "../App";
import { toast } from "sonner";

const METRIC_DESCRIPTIONS = {
  Correlation: "Measures how two stocks move together. +1 = perfectly together, -1 = opposite, 0 = no relationship.",
  "Z-Score": "How many standard deviations the current price ratio is from its mean. Above 2 or below -2 signals an extreme.",
  "Current Ratio": "The current price of stock A divided by stock B's price.",
  "Mean Ratio": "The average price ratio over the selected timeframe.",
  "Std Dev": "How much the price ratio typically varies day-to-day.",
  Stability: "How consistent the correlation has been. Higher = more reliable relationship.",
};

function getSignalColor(s) {
  switch (s) {
    case "SHORT_SPREAD": return "text-red-500";
    case "LONG_SPREAD": return "text-green-500";
    case "WATCH": return "text-yellow-500";
    default: return "text-zinc-400";
  }
}

function getSignalBg(s) {
  switch (s) {
    case "SHORT_SPREAD": return "bg-red-500/10 border-red-500/30";
    case "LONG_SPREAD": return "bg-green-500/10 border-green-500/30";
    case "WATCH": return "bg-yellow-500/10 border-yellow-500/30";
    default: return "bg-zinc-800/50 border-zinc-700/30";
  }
}

function getSignalIcon(s) {
  switch (s) {
    case "SHORT_SPREAD": return <TrendingDown className="w-5 h-5 text-red-500" />;
    case "LONG_SPREAD": return <TrendingUp className="w-5 h-5 text-green-500" />;
    case "WATCH": return <Activity className="w-5 h-5 text-yellow-500" />;
    default: return <Activity className="w-5 h-5 text-zinc-500" />;
  }
}

function getSignalLabel(signal, sym1, sym2) {
  switch (signal) {
    case "SHORT_SPREAD": return `${sym1} / ${sym2} — Spread Overbought (expected to fall)`;
    case "LONG_SPREAD": return `${sym1} / ${sym2} — Spread Oversold (expected to rise)`;
    case "WATCH": return "Approaching Threshold — Watch Closely";
    default: return "No Signal";
  }
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-xs shadow-xl">
      <p className="text-zinc-400 mb-1">{label}</p>
      {payload.map((entry, i) => (
        <p key={i} style={{ color: entry.color }}>
          {entry.name}: {typeof entry.value === "number" ? entry.value.toFixed(4) : entry.value}
        </p>
      ))}
    </div>
  );
}

export default function CorrelationPairDetail({ pair, onClose }) {
  if (!pair) return null;

  const {
    sym1, sym2,
    sym1_sector, sym2_sector,
    same_sector,
    current_correlation, z_score, current_ratio,
    mean_ratio, std_ratio, correlation_stability,
    signal, signal_reasoning,
    rolling_correlation, price_ratio,
    lead_lag, num_observations, timeframe_label,
  } = pair;

  return (
    <div className="bg-zinc-900/80 border border-zinc-700/50 rounded-xl p-3 sm:p-4 mt-4">
      {/* Header */}
      <div className="flex items-start justify-between mb-4 gap-2">
        <div className="flex flex-wrap items-center gap-2 min-w-0">
          <h3 className="text-sm font-semibold text-zinc-200 flex items-center gap-1.5">
            <span className="text-blue-400">{sym1}</span>
            <span className="text-zinc-600">/</span>
            <span className="text-orange-400">{sym2}</span>
          </h3>
          <span className={`text-[10px] px-1.5 py-0.5 rounded whitespace-nowrap ${
            same_sector ? "bg-zinc-800 text-zinc-400" : "bg-blue-900/30 text-blue-400"
          }`}>
            {same_sector ? "Same Sector" : "Cross Sector"}
          </span>
          <span className="text-[10px] text-zinc-600 whitespace-nowrap">
            {timeframe_label} · {num_observations} days
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-zinc-800 text-zinc-500 hover:text-zinc-300 flex-shrink-0"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Signal banner */}
      {signal && signal !== "NEUTRAL" && (
        <div className={`p-3 rounded-lg border mb-4 ${getSignalBg(signal)}`}>
          <div className="flex items-center gap-2 mb-1">
            {getSignalIcon(signal)}
            <span className={`text-sm font-bold ${getSignalColor(signal)}`}>
              {getSignalLabel(signal, sym1, sym2)}
            </span>
          </div>
          {signal_reasoning?.map((r, i) => (
            <p key={i} className="text-xs text-zinc-400 ml-7">{r}</p>
          ))}
        </div>
      )}

      {/* Metrics grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 sm:gap-3 mb-4">
        <MetricBox label="Correlation" value={(current_correlation * 100).toFixed(1)} unit="%" color={current_correlation > 0.7 ? "text-green-400" : current_correlation < 0.3 ? "text-red-400" : "text-yellow-400"} description={METRIC_DESCRIPTIONS.Correlation} />
        <MetricBox label="Z-Score" value={z_score?.toFixed(2)} color={Math.abs(z_score) > 2 ? "text-orange-400" : Math.abs(z_score) > 1 ? "text-yellow-400" : "text-zinc-300"} description={METRIC_DESCRIPTIONS["Z-Score"]} />
        <MetricBox label="Current Ratio" value={current_ratio?.toFixed(4)} description={METRIC_DESCRIPTIONS["Current Ratio"]} />
        <MetricBox label="Mean Ratio" value={mean_ratio?.toFixed(4)} color="text-zinc-400" description={METRIC_DESCRIPTIONS["Mean Ratio"]} />
        <MetricBox label="Std Dev" value={std_ratio?.toFixed(4)} color="text-zinc-400" description={METRIC_DESCRIPTIONS["Std Dev"]} />
        <MetricBox label="Stability" value={correlation_stability} unit="%" color={correlation_stability > 80 ? "text-green-400" : correlation_stability > 50 ? "text-yellow-400" : "text-red-400"} description={METRIC_DESCRIPTIONS.Stability} />
      </div>

      {/* Lead-lag info */}
      {lead_lag && lead_lag.leader && lead_lag.leader !== "Neither" && (
        <div className="flex items-center gap-2 mb-4 text-xs bg-zinc-800/50 rounded-lg px-3 py-2 flex-wrap">
          <TrendingUp className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" />
          <span className="text-zinc-300">
            <strong className="text-blue-400">{lead_lag.leader}</strong> typically leads{" "}
            <strong className="text-orange-400">{lead_lag.follower}</strong> by{" "}
            <strong>{lead_lag.lag_days}</strong> day{lead_lag.lag_days > 1 ? "s" : ""}
            <span className="text-zinc-600 ml-1">(cross-corr: {lead_lag.cross_correlation?.toFixed(2)})</span>
          </span>
        </div>
      )}

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div>
          <h4 className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-2">Price Ratio ({sym1} / {sym2})</h4>
          <div className="h-48 sm:h-52 bg-zinc-950 rounded-lg p-2 border border-zinc-800 min-w-0">
            <ResponsiveContainer width="100%" height="100%" minWidth={0}>
              <AreaChart data={price_ratio}>
                <defs><linearGradient id="ratioGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#3b82f6" stopOpacity={0.15} /><stop offset="95%" stopColor="#3b82f6" stopOpacity={0} /></linearGradient></defs>
                <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fill: "#52525b", fontSize: 9 }} tickFormatter={(v) => v?.slice(5) || ""} interval="preserveStartEnd" />
                <YAxis axisLine={false} tickLine={false} tick={{ fill: "#52525b", fontSize: 9 }} domain={["auto", "auto"]} />
                <Tooltip content={<CustomTooltip />} />
                <ReferenceLine y={mean_ratio} stroke="#71717a" strokeDasharray="3 3" strokeWidth={1} />
                <Area type="monotone" dataKey="ratio" stroke="#3b82f6" strokeWidth={1.5} fill="url(#ratioGrad)" dot={false} name="Ratio" />
                <Line type="monotone" dataKey="upper_band" stroke="#ef4444" strokeWidth={0.5} strokeDasharray="3 3" dot={false} name="Upper Band" />
                <Line type="monotone" dataKey="lower_band" stroke="#22c55e" strokeWidth={0.5} strokeDasharray="3 3" dot={false} name="Lower Band" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="flex flex-wrap justify-center gap-x-4 gap-y-1 mt-1 text-[9px] text-zinc-600">
            <span className="flex items-center gap-1"><span className="w-2 h-0.5 bg-blue-500" /> Ratio</span>
            <span className="flex items-center gap-1"><span className="w-2 h-0.5 bg-zinc-500 dashed" /> Mean</span>
            <span className="flex items-center gap-1"><span className="w-2 h-0.5 bg-red-500" /> Upper (2σ)</span>
            <span className="flex items-center gap-1"><span className="w-2 h-0.5 bg-green-500" /> Lower (2σ)</span>
          </div>
        </div>
        <div>
          <h4 className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-2">Rolling Correlation</h4>
          <div className="h-48 sm:h-52 bg-zinc-950 rounded-lg p-2 border border-zinc-800 min-w-0">
            <ResponsiveContainer width="100%" height="100%" minWidth={0}>
              <LineChart data={rolling_correlation}>
                <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fill: "#52525b", fontSize: 9 }} tickFormatter={(v) => v?.slice(5) || ""} interval="preserveStartEnd" />
                <YAxis domain={[-1, 1]} axisLine={false} tickLine={false} tick={{ fill: "#52525b", fontSize: 9 }} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
                <Tooltip content={<CustomTooltip />} />
                <ReferenceLine y={0} stroke="#52525b" strokeDasharray="3 3" />
                <ReferenceLine y={0.7} stroke="#22c55e" strokeDasharray="2 2" strokeWidth={0.5} />
                <ReferenceLine y={0.3} stroke="#eab308" strokeDasharray="2 2" strokeWidth={0.5} />
                <Line type="monotone" dataKey="correlation" stroke="#8b5cf6" strokeWidth={1.5} dot={false} name="Correlation" />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="flex flex-wrap justify-center gap-x-4 gap-y-1 mt-1 text-[9px] text-zinc-600">
            <span className="flex items-center gap-1"><span className="w-2 h-0.5 bg-violet-500" /> Rolling Corr</span>
            <span className="flex items-center gap-1"><span className="w-2 h-0.5 bg-green-600" /> High (0.7)</span>
            <span className="flex items-center gap-1"><span className="w-2 h-0.5 bg-yellow-600" /> Low (0.3)</span>
          </div>
        </div>
      </div>

      {/* ── Backtest Section ── */}
      <BacktestPanel sym1={sym1} sym2={sym2} />
    </div>
  );
}

function MetricBox({ label, value, unit, color, description }) {
  const [showTip, setShowTip] = useState(false);
  return (
    <div className="bg-zinc-800/50 rounded-lg px-2.5 sm:px-3 py-2 border border-zinc-800 relative">
      <div className="flex items-center gap-1 mb-0.5">
        <div className="text-[9px] text-zinc-600 uppercase tracking-wider">{label}</div>
        {description && (
          <div className="relative">
            <button onMouseEnter={() => setShowTip(true)} onMouseLeave={() => setShowTip(false)} onFocus={() => setShowTip(true)} onBlur={() => setShowTip(false)} className="text-zinc-700 hover:text-zinc-500 transition-colors">
              <HelpCircle className="w-2.5 h-2.5" />
            </button>
            {showTip && (
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 z-30 pointer-events-none">
                <div className="bg-zinc-800 border border-zinc-700 rounded-lg px-2.5 py-1.5 text-[10px] text-zinc-300 whitespace-normal w-48 shadow-xl">{description}</div>
              </div>
            )}
          </div>
        )}
      </div>
      <div className={`font-mono text-sm font-semibold ${color || "text-zinc-200"}`}>{value}{unit || ""}</div>
    </div>
  );
}

/* ────────────────────────────────────────────
   Backtest Panel — embedded in pair detail
   ──────────────────────────────────────────── */

const DEFAULT_PARAMS = {
  entry_z: 2.0, exit_z: 0.0, stop_z: 3.0, rolling_window: 20, days: 252, use_log_ratio: false,
  use_hedge_ratio: true, beta_window: 60,
  require_cointegrated: true, coint_pvalue: 0.05,
  transaction_cost_pct: 0.05,
};

function BacktestPanel({ sym1, sym2 }) {
  const [expanded, setExpanded] = useState(false);
  const [params, setParams] = useState(DEFAULT_PARAMS);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [showParams, setShowParams] = useState(false);

  const runBacktest = async () => {
    setRunning(true);
    setResult(null);
    try {
      const res = await axios.post(`${API}/correlation/backtest`, {
        sym1, sym2,
        days: params.days,
        entry_z: params.entry_z,
        exit_z: params.exit_z,
        stop_z: params.stop_z,
        rolling_window: params.rolling_window,
        use_log_ratio: params.use_log_ratio,
      }, { timeout: 60000 });
      setResult(res.data);
    } catch (err) {
      toast.error(`Backtest failed: ${err.response?.data?.detail || err.message}`);
    } finally {
      setRunning(false);
    }
  };

  if (!expanded) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className="mt-4 w-full flex items-center justify-center gap-2 py-2.5 rounded-lg border border-dashed border-zinc-700 text-xs text-zinc-400 hover:text-zinc-200 hover:border-zinc-600 hover:bg-zinc-800/30 transition-all"
      >
        <FlaskConical className="w-4 h-4" />
        Backtest Mean-Reversion Strategy
        <span className="text-[8px] text-zinc-600 ml-1">v2 — cointegration · hedge ratio · costs</span>
      </button>
    );
  }

  const metrics = result?.metrics;

  return (
    <div className="mt-4 border border-zinc-700/50 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2.5 bg-zinc-800/50 border-b border-zinc-700/50">
        <div className="flex items-center gap-2">
          <FlaskConical className="w-4 h-4 text-purple-400" />
          <span className="text-xs font-semibold text-zinc-300">Strategy Backtest</span>
          <span className="text-[10px] text-zinc-600">Mean reversion · {params.use_hedge_ratio ? 'β-spread' : 'ratio'}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setShowParams(!showParams)}
            className="p-1 rounded hover:bg-zinc-700 text-zinc-500 hover:text-zinc-300"
            title="Parameters"
          >
            <Settings2 className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={runBacktest}
            disabled={running}
            className="flex items-center gap-1 px-2.5 py-1 text-[10px] font-medium rounded bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white transition-colors"
          >
            <Play className={`w-3 h-3 ${running ? "animate-spin" : ""}`} />
            {running ? "Running..." : "Run"}
          </button>
        </div>
      </div>

      {/* Parameters (collapsible) */}
      {showParams && (
        <div className="px-3 py-2.5 bg-zinc-900/50 border-b border-zinc-800/50">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
            <ParamSlider label="Entry Z" value={params.entry_z} min={0.5} max={3.0} step={0.1} onChange={(v) => setParams(p => ({ ...p, entry_z: v }))} />
            <ParamSlider label="Exit Z" value={params.exit_z} min={0.0} max={1.5} step={0.1} onChange={(v) => setParams(p => ({ ...p, exit_z: v }))} />
            <ParamSlider label="Stop Z" value={params.stop_z} min={2.0} max={5.0} step={0.1} onChange={(v) => setParams(p => ({ ...p, stop_z: v }))} />
            <ParamSlider label="Window" value={params.rolling_window} min={10} max={60} step={5} onChange={(v) => setParams(p => ({ ...p, rolling_window: v }))} />
            <ParamSlider label="Days" value={params.days} min={60} max={756} step={30} onChange={(v) => setParams(p => ({ ...p, days: v }))} />
            <ParamSlider label="Cost %" value={params.transaction_cost_pct} min={0} max={0.5} step={0.01} onChange={(v) => setParams(p => ({ ...p, transaction_cost_pct: v }))} />
            <ParamSlider label="Beta Window" value={params.beta_window} min={20} max={120} step={10} onChange={(v) => setParams(p => ({ ...p, beta_window: v }))} />
            {/* Toggles row */}
            <div className="col-span-2 sm:col-span-3 lg:col-span-2 grid grid-cols-2 gap-2">
              <div className="flex flex-col gap-1">
                <label className="text-[9px] text-zinc-600 uppercase tracking-wider">Hedge Ratio (β)</label>
                <button
                  onClick={() => setParams(p => ({ ...p, use_hedge_ratio: !p.use_hedge_ratio }))}
                  className={`text-[10px] px-2 py-1.5 rounded font-medium transition-colors ${params.use_hedge_ratio ? "bg-purple-600 text-white" : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"}`}
                >
                  {params.use_hedge_ratio ? "ON" : "OFF"}
                </button>
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[9px] text-zinc-600 uppercase tracking-wider">Cointegration</label>
                <button
                  onClick={() => setParams(p => ({ ...p, require_cointegrated: !p.require_cointegrated }))}
                  className={`text-[10px] px-2 py-1.5 rounded font-medium transition-colors ${params.require_cointegrated ? "bg-purple-600 text-white" : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"}`}
                >
                  {params.require_cointegrated ? "ON" : "OFF"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Results */}
      {running && (
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin w-5 h-5 border-2 border-purple-500 border-t-transparent rounded-full mr-3" />
          <span className="text-sm text-zinc-400">Running backtest across {params.days} days...</span>
        </div>
      )}

      {result?.error && (
        <div className="p-4 text-sm text-yellow-400 bg-yellow-900/10">
          {result.error}
          {result.coint_info && (
            <div className="mt-1 text-xs text-zinc-500">
              Coint p-value: {result.coint_info.coint_pvalue} · Half-life: {result.coint_info.half_life_days}d
            </div>
          )}
        </div>
      )}

      {metrics && !result?.error && (
        <div className="p-3 space-y-3">
          {/* Strategy Info Banner */}
          {result.coint_info && (
            <div className={`text-[10px] flex items-center gap-2 px-2.5 py-1.5 rounded-lg ${
              result.coint_info.cointegrated
                ? "bg-green-900/20 text-green-400 border border-green-800/30"
                : "bg-yellow-900/20 text-yellow-400 border border-yellow-800/30"
            }`}>
              <span className="font-semibold">
                {result.coint_info.cointegrated ? "✓ Cointegrated" : "⚠ Not cointegrated"}
              </span>
              <span className="text-zinc-500">·</span>
              <span>p-value: {result.coint_info.coint_pvalue}</span>
              {result.coint_info.half_life_days > 0 && (
                <><span className="text-zinc-500">·</span><span>Half-life: {result.coint_info.half_life_days}d</span></>
              )}
              {result.spread_stats?.avg_beta && (
                <><span className="text-zinc-500">·</span><span>β = {result.spread_stats.avg_beta}</span></>
              )}
              <span className="text-zinc-500">·</span>
              <span>Cost: {result.params?.transaction_cost_pct || 0.05}%/side</span>
            </div>
          )}

          {/* Performance Metrics */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <MetricBox label="Total Return" value={`${metrics.total_return_pct > 0 ? "+" : ""}${metrics.total_return_pct}`} unit="%" color={metrics.total_return_pct > 0 ? "text-green-400" : "text-red-400"} />
            <MetricBox label="Ann. Return" value={`${metrics.annualized_return_pct > 0 ? "+" : ""}${metrics.annualized_return_pct}`} unit="%" color={metrics.annualized_return_pct > 0 ? "text-green-400" : "text-red-400"} />
            <MetricBox label="Sharpe Ratio" value={metrics.sharpe_ratio} color={metrics.sharpe_ratio > 1 ? "text-green-400" : metrics.sharpe_ratio > 0 ? "text-yellow-400" : "text-red-400"} />
            <MetricBox label="Max DD" value={metrics.max_drawdown_pct} unit="%" color={metrics.max_drawdown_pct < 15 ? "text-green-400" : metrics.max_drawdown_pct < 30 ? "text-yellow-400" : "text-red-400"} />
            <MetricBox label="Win Rate" value={metrics.win_rate} unit="%" color={metrics.win_rate > 50 ? "text-green-400" : "text-yellow-400"} />
            <MetricBox label="Trades" value={metrics.total_trades} />
            <MetricBox label="Profit Factor" value={metrics.profit_factor} color={metrics.profit_factor > 1.5 ? "text-green-400" : metrics.profit_factor > 1 ? "text-yellow-400" : "text-red-400"} />
            <MetricBox label="Avg Win" value={`${metrics.avg_win_pct > 0 ? "+" : ""}${metrics.avg_win_pct}`} unit="%" color="text-green-400" />
          </div>

          {/* Equity Curve Chart */}
          {result.equity_curve?.length > 0 && (
            <div>
              <h5 className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-1.5">Equity Curve</h5>
              <div className="h-36 bg-zinc-950 rounded-lg p-2 border border-zinc-800 min-w-0">
                <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                  <AreaChart data={result.equity_curve}>
                    <defs><linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#a855f7" stopOpacity={0.2} /><stop offset="95%" stopColor="#a855f7" stopOpacity={0} /></linearGradient></defs>
                    <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fill: "#52525b", fontSize: 8 }} tickFormatter={(v) => v?.slice(5) || ""} interval="preserveStartEnd" />
                    <YAxis axisLine={false} tickLine={false} tick={{ fill: "#52525b", fontSize: 8 }} domain={["auto", "auto"]} tickFormatter={(v) => `${v.toFixed(0)}`} />
                    <Tooltip content={<CustomTooltip />} />
                    <Area type="monotone" dataKey="equity" stroke="#a855f7" strokeWidth={1.5} fill="url(#eqGrad)" dot={false} name="Equity" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Trade Log */}
          {result.trades?.length > 0 && (
            <details className="group">
              <summary className="text-[10px] text-zinc-500 cursor-pointer hover:text-zinc-300 transition-colors">
                Trade Log ({result.trades.length} trades in view)
              </summary>
              <div className="mt-1 max-h-48 overflow-y-auto space-y-0.5">
                {[...result.trades].reverse().map((t, i) => (
                  <div key={i} className="flex items-center justify-between text-[10px] font-mono px-2 py-1 rounded hover:bg-zinc-800/50">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${t.pnl_pct > 0 ? "bg-green-500" : "bg-red-500"}`} />
                      <span className="text-zinc-500">{t.entry_date?.slice(5)}</span>
                      <span className={`text-zinc-400 ${t.side === "LONG_SPREAD" ? "text-green-400" : "text-red-400"}`}>
                        {t.side === "LONG_SPREAD" ? "LONG" : "SHORT"}
                      </span>
                      <span className="text-zinc-600">→ {t.exit_date?.slice(5)}</span>
                      <span className={`text-[8px] px-1 rounded ${t.exit_reason === "STOP_LOSS" ? "bg-red-900/30 text-red-400" : t.exit_reason === "TARGET" ? "bg-green-900/30 text-green-400" : "bg-zinc-800 text-zinc-500"}`}>
                        {t.exit_reason === "STOP_LOSS" ? "SL" : t.exit_reason === "TARGET" ? "TP" : "END"}
                      </span>
                    </div>
                    <span className={t.pnl_pct > 0 ? "text-green-400" : "text-red-400"}>
                      {t.pnl_pct > 0 ? "+" : ""}{t.pnl_pct}%
                    </span>
                    {t.cost_pct > 0 && (
                      <span className="text-zinc-700 text-[8px] ml-1">(-{(t.cost_pct || 0).toFixed(2)}% cost)</span>
                    )}
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}
    </div>
  );
}

function ParamSlider({ label, value, min, max, step, onChange }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-[9px] text-zinc-600 uppercase tracking-wider">{label}</label>
      <div className="flex items-center gap-1.5">
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          className="flex-1 h-1 accent-purple-500 cursor-pointer"
        />
        <span className="text-[10px] font-mono text-zinc-300 w-8 text-right">{value}</span>
      </div>
    </div>
  );
}
