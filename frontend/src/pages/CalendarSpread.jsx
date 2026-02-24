import { useState } from "react";
import axios from "axios";
import { API } from "../App";
import { Calendar, TrendingUp, ArrowRight } from "lucide-react";
import { toast } from "sonner";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

export default function CalendarSpread() {
  const [formData, setFormData] = useState({
    near_futures: "",
    far_futures: "",
    near_expiry_days: "",
    far_expiry_days: "",
  });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const calculateSpread = async () => {
    const { near_futures, far_futures, near_expiry_days, far_expiry_days } = formData;
    if (!near_futures || !far_futures || !near_expiry_days || !far_expiry_days) {
      toast.error("Please fill all required fields");
      return;
    }

    setLoading(true);
    try {
      const response = await axios.post(`${API}/arbitrage/calendar-spread`, null, {
        params: {
          near_futures: parseFloat(near_futures),
          far_futures: parseFloat(far_futures),
          near_expiry_days: parseInt(near_expiry_days),
          far_expiry_days: parseInt(far_expiry_days),
        },
      });
      setResult(response.data);
    } catch (error) {
      console.error("Error:", error);
      toast.error("Failed to calculate");
    } finally {
      setLoading(false);
    }
  };

  const formatPrice = (price) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      minimumFractionDigits: 2,
    }).format(price);
  };

  // Generate sample spread history data
  const spreadHistory = [
    { day: "Mon", spread: result ? result.spread * 0.9 : 20 },
    { day: "Tue", spread: result ? result.spread * 0.95 : 22 },
    { day: "Wed", spread: result ? result.spread * 1.05 : 25 },
    { day: "Thu", spread: result ? result.spread * 0.98 : 23 },
    { day: "Fri", spread: result ? result.spread : 24 },
  ];

  return (
    <div className="page-container" data-testid="calendar-spread-page">
      <div className="page-header">
        <h1 className="page-title">Calendar Spread Analysis</h1>
        <p className="page-subtitle">
          Analyze spread between near and far month futures contracts
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Input Form */}
        <div className="card" data-testid="calendar-form">
          <div className="card-header">
            <span className="card-title">Contract Details</span>
            <Calendar className="w-4 h-4 text-zinc-500" />
          </div>

          <div className="space-y-4">
            <div className="p-4 bg-zinc-900 rounded-lg">
              <h4 className="text-sm font-medium mb-3 text-blue-500">
                Near Month Contract
              </h4>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-zinc-500 mb-2">
                    Futures Price (₹) *
                  </label>
                  <input
                    type="number"
                    name="near_futures"
                    className="input"
                    placeholder="e.g., 22100"
                    value={formData.near_futures}
                    onChange={handleChange}
                    data-testid="near-futures-input"
                  />
                </div>
                <div>
                  <label className="block text-sm text-zinc-500 mb-2">
                    Days to Expiry *
                  </label>
                  <input
                    type="number"
                    name="near_expiry_days"
                    className="input"
                    placeholder="e.g., 7"
                    value={formData.near_expiry_days}
                    onChange={handleChange}
                    data-testid="near-days-input"
                  />
                </div>
              </div>
            </div>

            <div className="p-4 bg-zinc-900 rounded-lg">
              <h4 className="text-sm font-medium mb-3 text-purple-500">
                Far Month Contract
              </h4>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-zinc-500 mb-2">
                    Futures Price (₹) *
                  </label>
                  <input
                    type="number"
                    name="far_futures"
                    className="input"
                    placeholder="e.g., 22200"
                    value={formData.far_futures}
                    onChange={handleChange}
                    data-testid="far-futures-input"
                  />
                </div>
                <div>
                  <label className="block text-sm text-zinc-500 mb-2">
                    Days to Expiry *
                  </label>
                  <input
                    type="number"
                    name="far_expiry_days"
                    className="input"
                    placeholder="e.g., 37"
                    value={formData.far_expiry_days}
                    onChange={handleChange}
                    data-testid="far-days-input"
                  />
                </div>
              </div>
            </div>

            <button
              onClick={calculateSpread}
              className="btn btn-primary w-full"
              disabled={loading}
              data-testid="calculate-btn"
            >
              {loading ? "Calculating..." : "Analyze Spread"}
            </button>
          </div>
        </div>

        {/* Results */}
        <div className="card" data-testid="calendar-result">
          <div className="card-header">
            <span className="card-title">Spread Analysis</span>
            {result && (
              <span
                className={`badge ${
                  result.spread > 0 ? "badge-green" : "badge-red"
                }`}
              >
                {result.spread > 0 ? "Contango" : "Backwardation"}
              </span>
            )}
          </div>

          {result ? (
            <div className="space-y-4">
              {/* Visual Comparison */}
              <div className="flex items-center justify-between p-4 bg-zinc-900 rounded-lg">
                <div className="text-center">
                  <span className="text-xs text-zinc-500 block">Near Month</span>
                  <span className="font-mono text-lg font-bold text-blue-500">
                    {formatPrice(result.near_futures)}
                  </span>
                  <span className="text-xs text-zinc-500 block">
                    {result.near_expiry_days} days
                  </span>
                </div>
                <ArrowRight className="w-6 h-6 text-zinc-500" />
                <div className="text-center">
                  <span className="text-xs text-zinc-500 block">Far Month</span>
                  <span className="font-mono text-lg font-bold text-purple-500">
                    {formatPrice(result.far_futures)}
                  </span>
                  <span className="text-xs text-zinc-500 block">
                    {result.far_expiry_days} days
                  </span>
                </div>
              </div>

              {/* Metrics */}
              <div className="grid grid-cols-2 gap-4">
                <div className="stat-card">
                  <div className="stat-label">Spread</div>
                  <div
                    className={`stat-value ${
                      result.spread > 0 ? "text-green-500" : "text-red-500"
                    }`}
                  >
                    {formatPrice(result.spread)}
                  </div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Spread %</div>
                  <div
                    className={`stat-value ${
                      result.spread_pct > 0 ? "text-green-500" : "text-red-500"
                    }`}
                  >
                    {result.spread_pct}%
                  </div>
                </div>
              </div>

              <div className="stat-card">
                <div className="stat-label">Annualized Spread</div>
                <div className="stat-value text-yellow-500">
                  {result.annualized_spread}%
                </div>
              </div>

              {/* Strategy */}
              <div className="p-4 bg-blue-900/10 border border-blue-900/30 rounded-lg">
                <h4 className="text-sm font-medium text-blue-500 mb-2">
                  Recommended Strategy
                </h4>
                <p className="text-sm text-zinc-400">{result.strategy}</p>
              </div>

              {/* Spread Chart */}
              <div>
                <h4 className="text-sm font-medium mb-3">Spread History (Sample)</h4>
                <div className="h-32">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={spreadHistory}>
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
                      />
                      <Tooltip
                        contentStyle={{
                          background: "#1a1a1a",
                          border: "1px solid #262626",
                          borderRadius: "8px",
                        }}
                      />
                      <ReferenceLine y={0} stroke="#71717a" />
                      <Bar
                        dataKey="spread"
                        fill={result.spread > 0 ? "#22c55e" : "#ef4444"}
                        radius={[4, 4, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          ) : (
            <div className="empty-state">
              <Calendar className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
              <p>Enter contract details and click Analyze</p>
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
              Calendar Spread Trading
            </h3>
            <p className="text-sm text-zinc-400 mb-2">
              Calendar spreads profit from the difference between near and far
              month futures:
            </p>
            <ul className="text-sm text-zinc-400 list-disc list-inside space-y-1">
              <li>
                <strong>Contango</strong>: Far month &gt; Near month (normal
                market)
              </li>
              <li>
                <strong>Backwardation</strong>: Near month &gt; Far month
                (supply shortage)
              </li>
              <li>
                Profit when spread widens or narrows depending on your position
              </li>
              <li>Lower margin requirement than outright futures</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
