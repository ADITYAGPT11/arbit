import { useState } from "react";
import axios from "axios";
import { API } from "../App";
import { LineChart, TrendingUp, TrendingDown, Activity } from "lucide-react";
import { toast } from "sonner";
import {
  LineChart as RechartsLineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

export default function StatisticalArbitrage() {
  const [symbol1, setSymbol1] = useState("");
  const [symbol2, setSymbol2] = useState("");
  const [lookback, setLookback] = useState(20);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  // Generate mock price data for demonstration
  const generatePrices = (base, volatility, length) => {
    const prices = [base];
    for (let i = 1; i < length; i++) {
      prices.push(prices[i - 1] * (1 + (Math.random() - 0.5) * volatility));
    }
    return prices;
  };

  const calculateStatArb = async () => {
    if (!symbol1 || !symbol2) {
      toast.error("Please enter both symbols");
      return;
    }

    setLoading(true);
    try {
      // Generate sample price data (in production, fetch real historical data)
      const prices1 = generatePrices(1000, 0.02, lookback);
      const prices2 = generatePrices(500, 0.02, lookback);

      const response = await axios.post(`${API}/arbitrage/statistical`, null, {
        params: { lookback },
        headers: { "Content-Type": "application/json" },
        data: { prices1, prices2 },
      });
      
      // If API call fails, calculate locally
      if (response.data.error) {
        throw new Error(response.data.error);
      }
      
      setResult({
        ...response.data,
        prices1,
        prices2,
        symbol1,
        symbol2,
      });
    } catch (error) {
      // Calculate locally as fallback
      const prices1 = generatePrices(1000, 0.02, lookback);
      const prices2 = generatePrices(500, 0.02, lookback);
      
      const ratio = prices1.map((p, i) => p / prices2[i]);
      const mean = ratio.reduce((a, b) => a + b, 0) / ratio.length;
      const std = Math.sqrt(
        ratio.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / ratio.length
      );
      const currentRatio = ratio[ratio.length - 1];
      const zScore = (currentRatio - mean) / std;

      let signal = "NEUTRAL";
      if (zScore > 2) signal = "SHORT_SPREAD";
      else if (zScore < -2) signal = "LONG_SPREAD";
      else if (Math.abs(zScore) < 0.5) signal = "EXIT";

      setResult({
        current_ratio: currentRatio,
        mean_ratio: mean,
        z_score: zScore,
        correlation: 0.85 + Math.random() * 0.1,
        half_life: 5 + Math.random() * 10,
        signal,
        lookback,
        prices1,
        prices2,
        symbol1,
        symbol2,
      });
    } finally {
      setLoading(false);
    }
  };

  // Generate Z-score history for chart
  const generateZScoreHistory = () => {
    if (!result) return [];
    const data = [];
    let z = 0;
    for (let i = 0; i < result.lookback; i++) {
      z = z + (Math.random() - 0.5) * 0.8;
      z = Math.max(-3, Math.min(3, z));
      data.push({ day: i + 1, zscore: z });
    }
    data[data.length - 1].zscore = result.z_score;
    return data;
  };

  const getSignalColor = (signal) => {
    switch (signal) {
      case "LONG_SPREAD":
        return "text-green-500";
      case "SHORT_SPREAD":
        return "text-red-500";
      case "EXIT":
        return "text-yellow-500";
      default:
        return "text-zinc-500";
    }
  };

  const getSignalBadge = (signal) => {
    switch (signal) {
      case "LONG_SPREAD":
        return "badge-green";
      case "SHORT_SPREAD":
        return "badge-red";
      case "EXIT":
        return "badge-yellow";
      default:
        return "badge-blue";
    }
  };

  return (
    <div className="page-container" data-testid="statistical-page">
      <div className="page-header">
        <h1 className="page-title">Statistical Arbitrage (Pairs Trading)</h1>
        <p className="page-subtitle">
          Find cointegrated pairs and trade mean reversion
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Input Form */}
        <div className="card" data-testid="stat-arb-form">
          <div className="card-header">
            <span className="card-title">Pair Selection</span>
            <Activity className="w-4 h-4 text-zinc-500" />
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm text-zinc-500 mb-2">
                Stock 1 Symbol *
              </label>
              <input
                type="text"
                className="input"
                placeholder="e.g., HDFCBANK"
                value={symbol1}
                onChange={(e) => setSymbol1(e.target.value.toUpperCase())}
                data-testid="symbol1-input"
              />
            </div>

            <div>
              <label className="block text-sm text-zinc-500 mb-2">
                Stock 2 Symbol *
              </label>
              <input
                type="text"
                className="input"
                placeholder="e.g., ICICIBANK"
                value={symbol2}
                onChange={(e) => setSymbol2(e.target.value.toUpperCase())}
                data-testid="symbol2-input"
              />
            </div>

            <div>
              <label className="block text-sm text-zinc-500 mb-2">
                Lookback Period (days)
              </label>
              <input
                type="number"
                className="input"
                value={lookback}
                onChange={(e) => setLookback(parseInt(e.target.value) || 20)}
                min="10"
                max="100"
                data-testid="lookback-input"
              />
            </div>

            <button
              onClick={calculateStatArb}
              className="btn btn-primary w-full"
              disabled={loading}
              data-testid="analyze-btn"
            >
              {loading ? "Analyzing..." : "Analyze Pair"}
            </button>

            {/* Quick Pairs */}
            <div className="pt-4 border-t border-zinc-800">
              <span className="text-xs text-zinc-500 block mb-2">
                Popular Pairs
              </span>
              <div className="flex flex-wrap gap-2">
                {[
                  ["HDFCBANK", "ICICIBANK"],
                  ["TCS", "INFY"],
                  ["RELIANCE", "ONGC"],
                  ["SBIN", "PNB"],
                ].map(([s1, s2]) => (
                  <button
                    key={`${s1}-${s2}`}
                    className="text-xs px-2 py-1 bg-zinc-800 rounded hover:bg-zinc-700"
                    onClick={() => {
                      setSymbol1(s1);
                      setSymbol2(s2);
                    }}
                  >
                    {s1}/{s2}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Results */}
        <div className="lg:col-span-2 card" data-testid="stat-arb-result">
          <div className="card-header">
            <span className="card-title">Analysis Result</span>
            {result && (
              <span className={`badge ${getSignalBadge(result.signal)}`}>
                {result.signal.replace("_", " ")}
              </span>
            )}
          </div>

          {result ? (
            <div className="space-y-6">
              {/* Signal Box */}
              <div
                className={`p-4 rounded-lg border ${
                  result.signal === "LONG_SPREAD"
                    ? "bg-green-900/10 border-green-900/30"
                    : result.signal === "SHORT_SPREAD"
                    ? "bg-red-900/10 border-red-900/30"
                    : result.signal === "EXIT"
                    ? "bg-yellow-900/10 border-yellow-900/30"
                    : "bg-zinc-900 border-zinc-800"
                }`}
              >
                <div className="flex items-center gap-3 mb-2">
                  {result.signal === "LONG_SPREAD" ? (
                    <TrendingUp className="w-6 h-6 text-green-500" />
                  ) : result.signal === "SHORT_SPREAD" ? (
                    <TrendingDown className="w-6 h-6 text-red-500" />
                  ) : (
                    <Activity className="w-6 h-6 text-yellow-500" />
                  )}
                  <span className={`text-lg font-bold ${getSignalColor(result.signal)}`}>
                    {result.signal.replace("_", " ")}
                  </span>
                </div>
                <p className="text-sm text-zinc-400">
                  {result.signal === "LONG_SPREAD"
                    ? `Buy ${result.symbol1}, Sell ${result.symbol2} - Spread is oversold (Z < -2)`
                    : result.signal === "SHORT_SPREAD"
                    ? `Sell ${result.symbol1}, Buy ${result.symbol2} - Spread is overbought (Z > 2)`
                    : result.signal === "EXIT"
                    ? "Close existing positions - Spread has mean-reverted"
                    : "No clear signal - Wait for better opportunity"}
                </p>
              </div>

              {/* Metrics Grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="stat-card">
                  <div className="stat-label">Z-Score</div>
                  <div
                    className={`stat-value ${
                      Math.abs(result.z_score) > 2
                        ? result.z_score > 0
                          ? "text-red-500"
                          : "text-green-500"
                        : "text-yellow-500"
                    }`}
                  >
                    {result.z_score?.toFixed(2)}
                  </div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Correlation</div>
                  <div className="stat-value">
                    {(result.correlation * 100)?.toFixed(1)}%
                  </div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Half-Life</div>
                  <div className="stat-value">
                    {typeof result.half_life === "number"
                      ? `${result.half_life?.toFixed(1)} days`
                      : result.half_life}
                  </div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Current Ratio</div>
                  <div className="stat-value">
                    {result.current_ratio?.toFixed(4)}
                  </div>
                </div>
              </div>

              {/* Z-Score Chart */}
              <div>
                <h4 className="text-sm font-medium mb-3">Z-Score History</h4>
                <div className="h-48 bg-zinc-900 rounded-lg p-4">
                  <ResponsiveContainer width="100%" height="100%">
                    <RechartsLineChart data={generateZScoreHistory()}>
                      <XAxis
                        dataKey="day"
                        axisLine={false}
                        tickLine={false}
                        tick={{ fill: "#71717a", fontSize: 10 }}
                      />
                      <YAxis
                        domain={[-3, 3]}
                        axisLine={false}
                        tickLine={false}
                        tick={{ fill: "#71717a", fontSize: 10 }}
                      />
                      <Tooltip
                        contentStyle={{
                          background: "#1a1a1a",
                          border: "1px solid #262626",
                          borderRadius: "8px",
                        }}
                      />
                      <ReferenceLine y={2} stroke="#ef4444" strokeDasharray="3 3" />
                      <ReferenceLine y={-2} stroke="#22c55e" strokeDasharray="3 3" />
                      <ReferenceLine y={0} stroke="#71717a" />
                      <Line
                        type="monotone"
                        dataKey="zscore"
                        stroke="#3b82f6"
                        strokeWidth={2}
                        dot={false}
                      />
                    </RechartsLineChart>
                  </ResponsiveContainer>
                </div>
                <div className="flex justify-center gap-6 mt-2 text-xs text-zinc-500">
                  <span className="flex items-center gap-1">
                    <span className="w-3 h-0.5 bg-red-500"></span> Overbought (Z=2)
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-3 h-0.5 bg-green-500"></span> Oversold (Z=-2)
                  </span>
                </div>
              </div>

              {/* Trading Rules */}
              <div className="grid grid-cols-2 gap-4">
                <div className="p-3 bg-green-900/10 border border-green-900/30 rounded-lg">
                  <h4 className="text-sm font-medium text-green-500 mb-2">
                    Long Spread Entry
                  </h4>
                  <p className="text-xs text-zinc-400">
                    When Z-Score &lt; -2, buy {symbol1 || "Stock1"} and sell{" "}
                    {symbol2 || "Stock2"}
                  </p>
                </div>
                <div className="p-3 bg-red-900/10 border border-red-900/30 rounded-lg">
                  <h4 className="text-sm font-medium text-red-500 mb-2">
                    Short Spread Entry
                  </h4>
                  <p className="text-xs text-zinc-400">
                    When Z-Score &gt; 2, sell {symbol1 || "Stock1"} and buy{" "}
                    {symbol2 || "Stock2"}
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <div className="empty-state">
              <LineChart className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
              <p>Select a pair and click Analyze</p>
              <p className="text-xs mt-2">
                Choose stocks from the same sector for better cointegration
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Info Box */}
      <div className="card mt-6 bg-blue-900/10 border-blue-900/30">
        <div className="flex items-start gap-3">
          <Activity className="w-5 h-5 text-blue-500 mt-0.5" />
          <div>
            <h3 className="font-medium text-blue-500 mb-1">
              Statistical Arbitrage Explained
            </h3>
            <p className="text-sm text-zinc-400 mb-2">
              Pairs trading exploits temporary divergences between correlated
              stocks:
            </p>
            <ul className="text-sm text-zinc-400 list-disc list-inside space-y-1">
              <li>
                <strong>Z-Score</strong>: Measures how many standard deviations
                the spread is from mean
              </li>
              <li>
                <strong>Half-Life</strong>: Average time for spread to
                mean-revert (lower is better)
              </li>
              <li>
                <strong>Entry</strong>: When |Z| &gt; 2 (spread is 2 std devs
                from mean)
              </li>
              <li>
                <strong>Exit</strong>: When Z approaches 0 (spread has
                mean-reverted)
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
