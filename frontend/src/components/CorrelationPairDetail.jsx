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
} from "recharts";
import { X, TrendingUp, TrendingDown, Activity } from "lucide-react";

export default function CorrelationPairDetail({ pair, onClose }) {
  if (!pair) return null;

  const {
    sym1,
    sym2,
    sym1_sector,
    sym2_sector,
    same_sector,
    current_correlation,
    z_score,
    current_ratio,
    mean_ratio,
    std_ratio,
    correlation_stability,
    signal,
    signal_reasoning,
    rolling_correlation,
    price_ratio,
    lead_lag,
    num_observations,
    timeframe_label,
  } = pair;

  const getSignalColor = (s) => {
    switch (s) {
      case "SHORT_SPREAD": return "text-red-500";
      case "LONG_SPREAD": return "text-green-500";
      case "WATCH": return "text-yellow-500";
      default: return "text-zinc-400";
    }
  };

  const getSignalBg = (s) => {
    switch (s) {
      case "SHORT_SPREAD": return "bg-red-500/10 border-red-500/30";
      case "LONG_SPREAD": return "bg-green-500/10 border-green-500/30";
      case "WATCH": return "bg-yellow-500/10 border-yellow-500/30";
      default: return "bg-zinc-800/50 border-zinc-700/30";
    }
  };

  const getSignalIcon = (s) => {
    switch (s) {
      case "SHORT_SPREAD": return <TrendingDown className="w-5 h-5 text-red-500" />;
      case "LONG_SPREAD": return <TrendingUp className="w-5 h-5 text-green-500" />;
      case "WATCH": return <Activity className="w-5 h-5 text-yellow-500" />;
      default: return <Activity className="w-5 h-5 text-zinc-500" />;
    }
  };

  const CustomTooltip = ({ active, payload, label }) => {
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
  };

  return (
    <div className="bg-zinc-900/80 border border-zinc-700/50 rounded-xl p-4 mt-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-semibold text-zinc-200">
            <span className="text-blue-400">{sym1}</span>
            <span className="text-zinc-600 mx-1">/</span>
            <span className="text-orange-400">{sym2}</span>
          </h3>
          <span className={`text-[10px] px-1.5 py-0.5 rounded ${
            same_sector ? "bg-zinc-800 text-zinc-400" : "bg-blue-900/30 text-blue-400"
          }`}>
            {same_sector ? "Same Sector" : "Cross Sector"}
          </span>
          <span className="text-[10px] text-zinc-600">{timeframe_label} · {num_observations} days</span>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-zinc-800 text-zinc-500 hover:text-zinc-300"
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
              {signal === "SHORT_SPREAD" ? `${sym1} / ${sym2} Spread Overbought` :
               signal === "LONG_SPREAD" ? `${sym1} / ${sym2} Spread Oversold` :
               signal === "WATCH" ? "Approaching Threshold" : signal}
            </span>
          </div>
          {signal_reasoning?.map((r, i) => (
            <p key={i} className="text-xs text-zinc-400 ml-7">{r}</p>
          ))}
        </div>
      )}

      {/* Metrics grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 mb-4">
        <MetricBox label="Correlation" value={(current_correlation * 100).toFixed(1)} unit="%" color={current_correlation > 0.7 ? "text-green-400" : current_correlation < 0.3 ? "text-red-400" : "text-yellow-400"} />
        <MetricBox label="Z-Score" value={z_score?.toFixed(2)} color={Math.abs(z_score) > 2 ? "text-orange-400" : Math.abs(z_score) > 1 ? "text-yellow-400" : "text-zinc-300"} />
        <MetricBox label="Current Ratio" value={current_ratio?.toFixed(4)} />
        <MetricBox label="Mean Ratio" value={mean_ratio?.toFixed(4)} color="text-zinc-400" />
        <MetricBox label="Std Dev" value={std_ratio?.toFixed(4)} color="text-zinc-400" />
        <MetricBox label="Stability" value={correlation_stability} unit="%" color={correlation_stability > 80 ? "text-green-400" : correlation_stability > 50 ? "text-yellow-400" : "text-red-400"} />
      </div>

      {/* Lead-lag info */}
      {lead_lag && lead_lag.leader && lead_lag.leader !== "Neither" && (
        <div className="flex items-center gap-2 mb-4 text-xs bg-zinc-800/50 rounded-lg px-3 py-2">
          <TrendingUp className="w-3.5 h-3.5 text-blue-400" />
          <span className="text-zinc-300">
            <strong className="text-blue-400">{lead_lag.leader}</strong> typically leads{" "}
            <strong className="text-orange-400">{lead_lag.follower}</strong> by{" "}
            <strong>{lead_lag.lag_days}</strong> day{lead_lag.lag_days > 1 ? "s" : ""}
            <span className="text-zinc-600 ml-1">
              (cross-corr: {lead_lag.cross_correlation?.toFixed(2)})
            </span>
          </span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Price Ratio Chart */}
        <div>
          <h4 className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-2">
            Price Ratio ({sym1} / {sym2})
          </h4>
          <div className="h-48 bg-zinc-950 rounded-lg p-2 border border-zinc-800">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={price_ratio}>
                <defs>
                  <linearGradient id="ratioGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.15} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis
                  dataKey="date"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "#52525b", fontSize: 9 }}
                  tickFormatter={(v) => v?.slice(5) || ""}
                  interval="preserveStartEnd"
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "#52525b", fontSize: 9 }}
                  domain={["auto", "auto"]}
                />
                <Tooltip content={<CustomTooltip />} />
                <ReferenceLine y={mean_ratio} stroke="#71717a" strokeDasharray="3 3" strokeWidth={1} />
                <Area
                  type="monotone"
                  dataKey="ratio"
                  stroke="#3b82f6"
                  strokeWidth={1.5}
                  fill="url(#ratioGrad)"
                  dot={false}
                  name="Ratio"
                />
                <Line
                  type="monotone"
                  dataKey="upper_band"
                  stroke="#ef4444"
                  strokeWidth={0.5}
                  strokeDasharray="3 3"
                  dot={false}
                  name="Upper Band"
                />
                <Line
                  type="monotone"
                  dataKey="lower_band"
                  stroke="#22c55e"
                  strokeWidth={0.5}
                  strokeDasharray="3 3"
                  dot={false}
                  name="Lower Band"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="flex justify-center gap-4 mt-1 text-[9px] text-zinc-600">
            <span className="flex items-center gap-1">
              <span className="w-2 h-0.5 bg-blue-500" /> Ratio
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-0.5 bg-zinc-500 dashed" /> Mean
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-0.5 bg-red-500" /> Upper (2σ)
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-0.5 bg-green-500" /> Lower (2σ)
            </span>
          </div>
        </div>

        {/* Rolling Correlation Chart */}
        <div>
          <h4 className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-2">
            Rolling Correlation
          </h4>
          <div className="h-48 bg-zinc-950 rounded-lg p-2 border border-zinc-800">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={rolling_correlation}>
                <XAxis
                  dataKey="date"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "#52525b", fontSize: 9 }}
                  tickFormatter={(v) => v?.slice(5) || ""}
                  interval="preserveStartEnd"
                />
                <YAxis
                  domain={[-1, 1]}
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "#52525b", fontSize: 9 }}
                  tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                />
                <Tooltip content={<CustomTooltip />} />
                <ReferenceLine y={0} stroke="#52525b" strokeDasharray="3 3" />
                <ReferenceLine y={0.7} stroke="#22c55e" strokeDasharray="2 2" strokeWidth={0.5} />
                <ReferenceLine y={0.3} stroke="#eab308" strokeDasharray="2 2" strokeWidth={0.5} />
                <Line
                  type="monotone"
                  dataKey="correlation"
                  stroke="#8b5cf6"
                  strokeWidth={1.5}
                  dot={false}
                  name="Correlation"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="flex justify-center gap-4 mt-1 text-[9px] text-zinc-600">
            <span className="flex items-center gap-1">
              <span className="w-2 h-0.5 bg-violet-500" /> Rolling Corr
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-0.5 bg-green-600" /> High (0.7)
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-0.5 bg-yellow-600" /> Low (0.3)
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function MetricBox({ label, value, unit, color }) {
  return (
    <div className="bg-zinc-800/50 rounded-lg px-3 py-2 border border-zinc-800">
      <div className="text-[9px] text-zinc-600 uppercase tracking-wider mb-0.5">{label}</div>
      <div className={`font-mono text-sm font-semibold ${color || "text-zinc-200"}`}>
        {value}{unit || ""}
      </div>
    </div>
  );
}
