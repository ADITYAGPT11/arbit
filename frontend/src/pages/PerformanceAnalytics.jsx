import { useState, useEffect } from "react";
import axios from "axios";
import { API } from "../App";
import { BarChart3, TrendingUp, TrendingDown, Target } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  Cell,
} from "recharts";

export default function PerformanceAnalytics() {
  const [metrics, setMetrics] = useState(null);
  const [weekdayPerf, setWeekdayPerf] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadPerformanceData();
  }, []);

  const loadPerformanceData = async () => {
    setLoading(true);
    try {
      // Generate sample returns data
      const returns = Array.from({ length: 252 }, () => (Math.random() - 0.48) * 0.03);
      
      const metricsRes = await axios.post(`${API}/analytics/performance`, returns, {
        params: { risk_free_rate: 7.0 },
      });
      setMetrics(metricsRes.data);

      // Generate sample trades for weekday analysis
      const trades = [];
      for (let i = 0; i < 100; i++) {
        const date = new Date();
        date.setDate(date.getDate() - i);
        trades.push({
          date: date.toISOString(),
          pnl: (Math.random() - 0.45) * 10000,
        });
      }

      const weekdayRes = await axios.post(`${API}/analytics/weekday`, trades);
      setWeekdayPerf(weekdayRes.data);
    } catch (error) {
      console.error("Error loading performance data:", error);
      // Set fallback data
      setMetrics({
        total_return: 24.5,
        avg_daily_return: 0.097,
        volatility: 18.2,
        sharpe_ratio: 1.45,
        sortino_ratio: 2.1,
        max_drawdown: -12.5,
        calmar_ratio: 1.96,
        win_rate: 58.3,
        profit_factor: 1.65,
        total_trades: 252,
      });
      setWeekdayPerf({
        Monday: { total_pnl: 15000, avg_pnl: 750, trade_count: 20, win_rate: 55 },
        Tuesday: { total_pnl: 22000, avg_pnl: 1100, trade_count: 20, win_rate: 60 },
        Wednesday: { total_pnl: 8000, avg_pnl: 400, trade_count: 20, win_rate: 50 },
        Thursday: { total_pnl: 35000, avg_pnl: 1750, trade_count: 20, win_rate: 70 },
        Friday: { total_pnl: 12000, avg_pnl: 600, trade_count: 20, win_rate: 55 },
      });
    } finally {
      setLoading(false);
    }
  };

  // Generate equity curve data
  const generateEquityCurve = () => {
    const data = [];
    let equity = 1000000;
    for (let i = 0; i < 252; i++) {
      equity = equity * (1 + (Math.random() - 0.48) * 0.015);
      data.push({
        day: i + 1,
        equity: Math.round(equity),
        drawdown: Math.round((equity / Math.max(...data.map((d) => d?.equity || equity), equity) - 1) * 100 * 10) / 10,
      });
    }
    return data;
  };

  const equityCurve = generateEquityCurve();

  // Prepare weekday chart data
  const weekdayChartData = weekdayPerf
    ? Object.entries(weekdayPerf).map(([day, data]) => ({
        day: day.slice(0, 3),
        pnl: data.total_pnl,
        winRate: data.win_rate,
      }))
    : [];

  const formatCurrency = (value) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  if (loading) {
    return (
      <div className="page-container">
        <div className="loading-container">
          <div className="loading-spinner"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container" data-testid="performance-page">
      <div className="page-header">
        <h1 className="page-title">Performance Analytics</h1>
        <p className="page-subtitle">
          Comprehensive trading performance metrics and analysis
        </p>
      </div>

      {/* Key Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
        <div className="stat-card" data-testid="total-return">
          <div className="stat-label">Total Return</div>
          <div
            className={`stat-value ${
              metrics?.total_return >= 0 ? "text-green-500" : "text-red-500"
            }`}
          >
            {metrics?.total_return >= 0 ? "+" : ""}
            {metrics?.total_return}%
          </div>
        </div>
        <div className="stat-card" data-testid="sharpe-ratio">
          <div className="stat-label">Sharpe Ratio</div>
          <div
            className={`stat-value ${
              metrics?.sharpe_ratio >= 1 ? "text-green-500" : "text-yellow-500"
            }`}
          >
            {metrics?.sharpe_ratio}
          </div>
        </div>
        <div className="stat-card" data-testid="sortino-ratio">
          <div className="stat-label">Sortino Ratio</div>
          <div className="stat-value">{metrics?.sortino_ratio}</div>
        </div>
        <div className="stat-card" data-testid="max-drawdown">
          <div className="stat-label">Max Drawdown</div>
          <div className="stat-value text-red-500">{metrics?.max_drawdown}%</div>
        </div>
        <div className="stat-card" data-testid="win-rate">
          <div className="stat-label">Win Rate</div>
          <div
            className={`stat-value ${
              metrics?.win_rate >= 50 ? "text-green-500" : "text-red-500"
            }`}
          >
            {metrics?.win_rate}%
          </div>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Equity Curve */}
        <div className="card" data-testid="equity-curve">
          <div className="card-header">
            <span className="card-title">Equity Curve</span>
            <TrendingUp className="w-4 h-4 text-green-500" />
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={equityCurve}>
                <defs>
                  <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
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
                  stroke="#22c55e"
                  fill="url(#equityGradient)"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Drawdown Chart */}
        <div className="card" data-testid="drawdown-chart">
          <div className="card-header">
            <span className="card-title">Drawdown</span>
            <TrendingDown className="w-4 h-4 text-red-500" />
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={equityCurve}>
                <defs>
                  <linearGradient id="drawdownGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
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
                  tickFormatter={(v) => `${v}%`}
                />
                <Tooltip
                  contentStyle={{
                    background: "#1a1a1a",
                    border: "1px solid #262626",
                    borderRadius: "8px",
                  }}
                  formatter={(value) => [`${value}%`, "Drawdown"]}
                />
                <Area
                  type="monotone"
                  dataKey="drawdown"
                  stroke="#ef4444"
                  fill="url(#drawdownGradient)"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Weekday Performance */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="card" data-testid="weekday-pnl">
          <div className="card-header">
            <span className="card-title">PnL by Weekday</span>
            <BarChart3 className="w-4 h-4 text-zinc-500" />
          </div>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={weekdayChartData}>
                <XAxis
                  dataKey="day"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "#71717a", fontSize: 12 }}
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "#71717a", fontSize: 10 }}
                  tickFormatter={(v) => `${(v / 1000).toFixed(0)}K`}
                />
                <Tooltip
                  contentStyle={{
                    background: "#1a1a1a",
                    border: "1px solid #262626",
                    borderRadius: "8px",
                  }}
                  formatter={(value) => [formatCurrency(value), "PnL"]}
                />
                <Bar dataKey="pnl" radius={[4, 4, 0, 0]}>
                  {weekdayChartData.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={entry.pnl >= 0 ? "#22c55e" : "#ef4444"}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card" data-testid="weekday-winrate">
          <div className="card-header">
            <span className="card-title">Win Rate by Weekday</span>
            <Target className="w-4 h-4 text-zinc-500" />
          </div>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={weekdayChartData}>
                <XAxis
                  dataKey="day"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "#71717a", fontSize: 12 }}
                />
                <YAxis
                  domain={[0, 100]}
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "#71717a", fontSize: 10 }}
                  tickFormatter={(v) => `${v}%`}
                />
                <Tooltip
                  contentStyle={{
                    background: "#1a1a1a",
                    border: "1px solid #262626",
                    borderRadius: "8px",
                  }}
                  formatter={(value) => [`${value}%`, "Win Rate"]}
                />
                <Bar dataKey="winRate" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Detailed Metrics */}
      <div className="card" data-testid="detailed-metrics">
        <div className="card-header">
          <span className="card-title">Detailed Metrics</span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="data-row flex-col items-start">
            <span className="data-label">Avg Daily Return</span>
            <span className="data-value">{metrics?.avg_daily_return}%</span>
          </div>
          <div className="data-row flex-col items-start">
            <span className="data-label">Volatility (Ann.)</span>
            <span className="data-value">{metrics?.volatility}%</span>
          </div>
          <div className="data-row flex-col items-start">
            <span className="data-label">Calmar Ratio</span>
            <span className="data-value">{metrics?.calmar_ratio}</span>
          </div>
          <div className="data-row flex-col items-start">
            <span className="data-label">Profit Factor</span>
            <span className="data-value">{metrics?.profit_factor}</span>
          </div>
          <div className="data-row flex-col items-start">
            <span className="data-label">Total Trades</span>
            <span className="data-value">{metrics?.total_trades}</span>
          </div>
          <div className="data-row flex-col items-start">
            <span className="data-label">Best Weekday</span>
            <span className="data-value text-green-500">Thursday</span>
          </div>
          <div className="data-row flex-col items-start">
            <span className="data-label">Worst Weekday</span>
            <span className="data-value text-red-500">Wednesday</span>
          </div>
          <div className="data-row flex-col items-start">
            <span className="data-label">Risk-Free Rate</span>
            <span className="data-value">7.0%</span>
          </div>
        </div>
      </div>
    </div>
  );
}
