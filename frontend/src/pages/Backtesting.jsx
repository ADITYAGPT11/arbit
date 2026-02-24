import { useState } from "react";
import axios from "axios";
import { API } from "../App";
import { History, Play, Download, TrendingUp } from "lucide-react";
import { toast } from "sonner";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from "recharts";

export default function Backtesting() {
  const [formData, setFormData] = useState({
    strategy: "cross_exchange",
    symbol: "RELIANCE",
    start_date: "2024-01-01",
    end_date: "2024-12-31",
    initial_capital: "1000000",
  });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const strategies = [
    { value: "cross_exchange", label: "Cross-Exchange Arbitrage" },
    { value: "cash_carry", label: "Cash & Carry Arbitrage" },
    { value: "statistical", label: "Statistical Arbitrage" },
    { value: "calendar", label: "Calendar Spread" },
  ];

  const runBacktest = async () => {
    setLoading(true);
    try {
      const response = await axios.post(`${API}/backtest`, {
        strategy: formData.strategy,
        symbol: formData.symbol,
        start_date: formData.start_date,
        end_date: formData.end_date,
        initial_capital: parseFloat(formData.initial_capital),
      });
      setResult(response.data);
      toast.success("Backtest completed!");
    } catch (error) {
      console.error("Backtest error:", error);
      toast.error("Backtest failed");
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (value) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const downloadReport = () => {
    if (!result) return;

    const report = {
      ...result,
      generated_at: new Date().toISOString(),
    };

    const blob = new Blob([JSON.stringify(report, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `backtest_${result.strategy}_${result.symbol}_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="page-container" data-testid="backtest-page">
      <div className="page-header">
        <h1 className="page-title">Backtesting</h1>
        <p className="page-subtitle">
          Test arbitrage strategies on historical data
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Configuration */}
        <div className="card" data-testid="backtest-form">
          <div className="card-header">
            <span className="card-title">Backtest Configuration</span>
            <History className="w-4 h-4 text-zinc-500" />
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm text-zinc-500 mb-2">
                Strategy
              </label>
              <select
                className="select"
                value={formData.strategy}
                onChange={(e) =>
                  setFormData({ ...formData, strategy: e.target.value })
                }
                data-testid="strategy-select"
              >
                {strategies.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm text-zinc-500 mb-2">Symbol</label>
              <input
                type="text"
                className="input"
                value={formData.symbol}
                onChange={(e) =>
                  setFormData({ ...formData, symbol: e.target.value.toUpperCase() })
                }
                data-testid="symbol-input"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-zinc-500 mb-2">
                  Start Date
                </label>
                <input
                  type="date"
                  className="input"
                  value={formData.start_date}
                  onChange={(e) =>
                    setFormData({ ...formData, start_date: e.target.value })
                  }
                  data-testid="start-date"
                />
              </div>
              <div>
                <label className="block text-sm text-zinc-500 mb-2">
                  End Date
                </label>
                <input
                  type="date"
                  className="input"
                  value={formData.end_date}
                  onChange={(e) =>
                    setFormData({ ...formData, end_date: e.target.value })
                  }
                  data-testid="end-date"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm text-zinc-500 mb-2">
                Initial Capital (₹)
              </label>
              <input
                type="number"
                className="input"
                value={formData.initial_capital}
                onChange={(e) =>
                  setFormData({ ...formData, initial_capital: e.target.value })
                }
                data-testid="capital-input"
              />
            </div>

            <button
              onClick={runBacktest}
              className="btn btn-primary w-full flex items-center justify-center gap-2"
              disabled={loading}
              data-testid="run-backtest-btn"
            >
              {loading ? (
                <>
                  <span className="animate-spin">⏳</span>
                  Running...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  Run Backtest
                </>
              )}
            </button>
          </div>
        </div>

        {/* Results */}
        <div className="lg:col-span-2 space-y-6">
          {result ? (
            <>
              {/* Summary */}
              <div className="card" data-testid="backtest-summary">
                <div className="card-header">
                  <span className="card-title">Backtest Results</span>
                  <button
                    onClick={downloadReport}
                    className="btn btn-secondary flex items-center gap-2"
                    data-testid="download-btn"
                  >
                    <Download className="w-4 h-4" />
                    Download
                  </button>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                  <div className="stat-card">
                    <div className="stat-label">Final Capital</div>
                    <div
                      className={`stat-value ${
                        result.final_capital > result.initial_capital
                          ? "text-green-500"
                          : "text-red-500"
                      }`}
                    >
                      {formatCurrency(result.final_capital)}
                    </div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-label">Total Return</div>
                    <div
                      className={`stat-value ${
                        result.total_return_pct >= 0
                          ? "text-green-500"
                          : "text-red-500"
                      }`}
                    >
                      {result.total_return_pct >= 0 ? "+" : ""}
                      {result.total_return_pct}%
                    </div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-label">Sharpe Ratio</div>
                    <div className="stat-value">
                      {result.metrics?.sharpe_ratio || "—"}
                    </div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-label">Max Drawdown</div>
                    <div className="stat-value text-red-500">
                      {result.metrics?.max_drawdown || "—"}%
                    </div>
                  </div>
                </div>

                {/* Equity Curve */}
                <div>
                  <h4 className="text-sm font-medium mb-3">Equity Curve</h4>
                  <div className="h-48 bg-zinc-900 rounded-lg p-4">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart
                        data={result.equity_curve.map((v, i) => ({
                          day: i * 5,
                          equity: v,
                        }))}
                      >
                        <defs>
                          <linearGradient
                            id="equityGradient"
                            x1="0"
                            y1="0"
                            x2="0"
                            y2="1"
                          >
                            <stop
                              offset="5%"
                              stopColor={
                                result.total_return_pct >= 0
                                  ? "#22c55e"
                                  : "#ef4444"
                              }
                              stopOpacity={0.3}
                            />
                            <stop
                              offset="95%"
                              stopColor={
                                result.total_return_pct >= 0
                                  ? "#22c55e"
                                  : "#ef4444"
                              }
                              stopOpacity={0}
                            />
                          </linearGradient>
                        </defs>
                        <XAxis
                          dataKey="day"
                          axisLine={false}
                          tickLine={false}
                          tick={{ fill: "#71717a", fontSize: 10 }}
                        />
                        <YAxis
                          axisLine={false}
                          tickLine={false}
                          tick={{ fill: "#71717a", fontSize: 10 }}
                          tickFormatter={(v) => `${(v / 100000).toFixed(0)}L`}
                        />
                        <Tooltip
                          contentStyle={{
                            background: "#1a1a1a",
                            border: "1px solid #262626",
                            borderRadius: "8px",
                          }}
                          formatter={(value) => [formatCurrency(value), "Equity"]}
                        />
                        <Area
                          type="monotone"
                          dataKey="equity"
                          stroke={
                            result.total_return_pct >= 0 ? "#22c55e" : "#ef4444"
                          }
                          fill="url(#equityGradient)"
                          strokeWidth={2}
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>

              {/* Metrics */}
              <div className="card" data-testid="backtest-metrics">
                <div className="card-header">
                  <span className="card-title">Performance Metrics</span>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="data-row flex-col items-start">
                    <span className="data-label">Win Rate</span>
                    <span className="data-value">
                      {result.metrics?.win_rate || "—"}%
                    </span>
                  </div>
                  <div className="data-row flex-col items-start">
                    <span className="data-label">Sortino Ratio</span>
                    <span className="data-value">
                      {result.metrics?.sortino_ratio || "—"}
                    </span>
                  </div>
                  <div className="data-row flex-col items-start">
                    <span className="data-label">Calmar Ratio</span>
                    <span className="data-value">
                      {result.metrics?.calmar_ratio || "—"}
                    </span>
                  </div>
                  <div className="data-row flex-col items-start">
                    <span className="data-label">Profit Factor</span>
                    <span className="data-value">
                      {result.metrics?.profit_factor || "—"}
                    </span>
                  </div>
                  <div className="data-row flex-col items-start">
                    <span className="data-label">Total Trades</span>
                    <span className="data-value">{result.total_trades}</span>
                  </div>
                  <div className="data-row flex-col items-start">
                    <span className="data-label">Volatility</span>
                    <span className="data-value">
                      {result.metrics?.volatility || "—"}%
                    </span>
                  </div>
                  <div className="data-row flex-col items-start">
                    <span className="data-label">Avg Daily Return</span>
                    <span className="data-value">
                      {result.metrics?.avg_daily_return || "—"}%
                    </span>
                  </div>
                  <div className="data-row flex-col items-start">
                    <span className="data-label">Strategy</span>
                    <span className="data-value capitalize">
                      {result.strategy.replace("_", " ")}
                    </span>
                  </div>
                </div>
              </div>

              {/* Trade Log */}
              <div className="card" data-testid="trade-log">
                <div className="card-header">
                  <span className="card-title">Recent Trades</span>
                  <span className="badge badge-blue">
                    {result.trades.length} shown
                  </span>
                </div>
                <div className="overflow-x-auto">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Action</th>
                        <th>Price</th>
                        <th>Qty</th>
                        <th>PnL</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.trades.slice(0, 10).map((trade, idx) => (
                        <tr key={idx}>
                          <td>
                            {new Date(trade.date).toLocaleDateString("en-IN")}
                          </td>
                          <td>
                            <span
                              className={`badge ${
                                trade.action === "BUY"
                                  ? "badge-green"
                                  : "badge-red"
                              }`}
                            >
                              {trade.action}
                            </span>
                          </td>
                          <td>{formatCurrency(trade.price)}</td>
                          <td>{trade.quantity}</td>
                          <td
                            className={
                              trade.pnl >= 0 ? "text-green-500" : "text-red-500"
                            }
                          >
                            {formatCurrency(trade.pnl)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          ) : (
            <div className="card">
              <div className="empty-state">
                <History className="w-16 h-16 text-zinc-600 mx-auto mb-4" />
                <p className="text-lg">Configure and run a backtest</p>
                <p className="text-sm mt-2 text-zinc-500">
                  Select a strategy, symbol, and date range to analyze
                  historical performance
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Info Box */}
      <div className="card mt-6 bg-blue-900/10 border-blue-900/30">
        <div className="flex items-start gap-3">
          <TrendingUp className="w-5 h-5 text-blue-500 mt-0.5" />
          <div>
            <h3 className="font-medium text-blue-500 mb-1">
              Backtesting Notes
            </h3>
            <ul className="text-sm text-zinc-400 list-disc list-inside space-y-1">
              <li>
                Results include transaction costs (STT, brokerage, stamp duty)
              </li>
              <li>Slippage is estimated based on typical market conditions</li>
              <li>Past performance does not guarantee future results</li>
              <li>
                Use Monte Carlo simulation for more robust risk assessment
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
