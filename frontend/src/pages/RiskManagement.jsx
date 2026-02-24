import { useState } from "react";
import axios from "axios";
import { API } from "../App";
import { Shield, Calculator, AlertTriangle, DollarSign } from "lucide-react";
import { toast } from "sonner";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

export default function RiskManagement() {
  const [positionForm, setPositionForm] = useState({
    capital: "1000000",
    risk_per_trade: "2",
    stop_loss_pct: "1",
    price: "",
  });
  const [varForm, setVarForm] = useState({
    portfolio_value: "1000000",
    confidence: "95",
  });
  const [marginForm, setMarginForm] = useState({
    position_value: "",
    volatility: "15",
    is_futures: true,
  });

  const [positionResult, setPositionResult] = useState(null);
  const [varResult, setVarResult] = useState(null);
  const [marginResult, setMarginResult] = useState(null);

  const calculatePositionSize = async () => {
    if (!positionForm.price) {
      toast.error("Please enter stock price");
      return;
    }

    try {
      const response = await axios.post(`${API}/risk/position-size`, null, {
        params: {
          capital: parseFloat(positionForm.capital),
          risk_per_trade: parseFloat(positionForm.risk_per_trade),
          stop_loss_pct: parseFloat(positionForm.stop_loss_pct),
          price: parseFloat(positionForm.price),
        },
      });
      setPositionResult(response.data);
    } catch (error) {
      toast.error("Failed to calculate position size");
    }
  };

  const calculateVaR = async () => {
    try {
      // Generate sample returns
      const returns = Array.from({ length: 100 }, () => (Math.random() - 0.5) * 0.04);
      
      const response = await axios.post(`${API}/risk/var`, returns, {
        params: {
          confidence: parseFloat(varForm.confidence) / 100,
          portfolio_value: parseFloat(varForm.portfolio_value),
        },
      });
      setVarResult(response.data);
    } catch (error) {
      toast.error("Failed to calculate VaR");
    }
  };

  const calculateMargin = async () => {
    if (!marginForm.position_value) {
      toast.error("Please enter position value");
      return;
    }

    try {
      const response = await axios.post(`${API}/risk/margin`, null, {
        params: {
          position_value: parseFloat(marginForm.position_value),
          volatility: parseFloat(marginForm.volatility),
          is_futures: marginForm.is_futures,
        },
      });
      setMarginResult(response.data);
    } catch (error) {
      toast.error("Failed to calculate margin");
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

  // Pie chart data for margin breakdown
  const marginPieData = marginResult
    ? [
        { name: "SPAN Margin", value: marginResult.span_margin, color: "#3b82f6" },
        { name: "Exposure Margin", value: marginResult.exposure_margin, color: "#8b5cf6" },
      ]
    : [];

  return (
    <div className="page-container" data-testid="risk-page">
      <div className="page-header">
        <h1 className="page-title">Risk Management</h1>
        <p className="page-subtitle">
          Position sizing, VaR calculation, and margin requirements
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Position Size Calculator */}
        <div className="card" data-testid="position-size-calc">
          <div className="card-header">
            <span className="card-title">Position Size Calculator</span>
            <Calculator className="w-4 h-4 text-zinc-500" />
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm text-zinc-500 mb-2">
                Total Capital (₹)
              </label>
              <input
                type="number"
                className="input"
                value={positionForm.capital}
                onChange={(e) =>
                  setPositionForm({ ...positionForm, capital: e.target.value })
                }
              />
            </div>
            <div>
              <label className="block text-sm text-zinc-500 mb-2">
                Risk Per Trade (%)
              </label>
              <input
                type="number"
                className="input"
                value={positionForm.risk_per_trade}
                onChange={(e) =>
                  setPositionForm({ ...positionForm, risk_per_trade: e.target.value })
                }
                step="0.5"
              />
            </div>
            <div>
              <label className="block text-sm text-zinc-500 mb-2">
                Stop Loss (%)
              </label>
              <input
                type="number"
                className="input"
                value={positionForm.stop_loss_pct}
                onChange={(e) =>
                  setPositionForm({ ...positionForm, stop_loss_pct: e.target.value })
                }
                step="0.5"
              />
            </div>
            <div>
              <label className="block text-sm text-zinc-500 mb-2">
                Stock Price (₹)
              </label>
              <input
                type="number"
                className="input"
                placeholder="e.g., 2500"
                value={positionForm.price}
                onChange={(e) =>
                  setPositionForm({ ...positionForm, price: e.target.value })
                }
              />
            </div>
            <button
              onClick={calculatePositionSize}
              className="btn btn-primary w-full"
            >
              Calculate
            </button>

            {positionResult && (
              <div className="mt-4 p-4 bg-zinc-900 rounded-lg">
                <div className="text-center mb-3">
                  <span className="text-xs text-zinc-500">Recommended Shares</span>
                  <div className="text-3xl font-bold text-green-500">
                    {positionResult.recommended_shares}
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <span className="text-zinc-500">Position Value:</span>
                    <span className="ml-2 font-mono">
                      {formatCurrency(positionResult.position_value)}
                    </span>
                  </div>
                  <div>
                    <span className="text-zinc-500">Risk Amount:</span>
                    <span className="ml-2 font-mono text-red-500">
                      {formatCurrency(positionResult.risk_amount)}
                    </span>
                  </div>
                  <div className="col-span-2">
                    <span className="text-zinc-500">Capital Utilization:</span>
                    <span className="ml-2 font-mono">
                      {positionResult.capital_utilization_pct}%
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* VaR Calculator */}
        <div className="card" data-testid="var-calc">
          <div className="card-header">
            <span className="card-title">Value at Risk (VaR)</span>
            <AlertTriangle className="w-4 h-4 text-yellow-500" />
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm text-zinc-500 mb-2">
                Portfolio Value (₹)
              </label>
              <input
                type="number"
                className="input"
                value={varForm.portfolio_value}
                onChange={(e) =>
                  setVarForm({ ...varForm, portfolio_value: e.target.value })
                }
              />
            </div>
            <div>
              <label className="block text-sm text-zinc-500 mb-2">
                Confidence Level (%)
              </label>
              <select
                className="select"
                value={varForm.confidence}
                onChange={(e) =>
                  setVarForm({ ...varForm, confidence: e.target.value })
                }
              >
                <option value="90">90%</option>
                <option value="95">95%</option>
                <option value="99">99%</option>
              </select>
            </div>
            <button onClick={calculateVaR} className="btn btn-primary w-full">
              Calculate VaR
            </button>

            {varResult && (
              <div className="mt-4 space-y-4">
                <div className="p-4 bg-red-900/10 border border-red-900/30 rounded-lg">
                  <span className="text-xs text-zinc-500 block mb-1">
                    Historical VaR ({varResult.confidence_level}% confidence)
                  </span>
                  <div className="text-2xl font-bold text-red-500">
                    {formatCurrency(varResult.historical_var_amount)}
                  </div>
                  <span className="text-xs text-zinc-500">
                    ({varResult.historical_var_pct}% of portfolio)
                  </span>
                </div>
                <div className="p-4 bg-yellow-900/10 border border-yellow-900/30 rounded-lg">
                  <span className="text-xs text-zinc-500 block mb-1">
                    Parametric VaR
                  </span>
                  <div className="text-2xl font-bold text-yellow-500">
                    {formatCurrency(varResult.parametric_var_amount)}
                  </div>
                  <span className="text-xs text-zinc-500">
                    ({varResult.parametric_var_pct}% of portfolio)
                  </span>
                </div>
                <p className="text-xs text-zinc-500">
                  * Maximum expected loss on {varResult.confidence_level}% of trading days
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Margin Calculator */}
        <div className="card" data-testid="margin-calc">
          <div className="card-header">
            <span className="card-title">Margin Calculator</span>
            <DollarSign className="w-4 h-4 text-zinc-500" />
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm text-zinc-500 mb-2">
                Position Value (₹)
              </label>
              <input
                type="number"
                className="input"
                placeholder="e.g., 500000"
                value={marginForm.position_value}
                onChange={(e) =>
                  setMarginForm({ ...marginForm, position_value: e.target.value })
                }
              />
            </div>
            <div>
              <label className="block text-sm text-zinc-500 mb-2">
                Volatility (%)
              </label>
              <input
                type="number"
                className="input"
                value={marginForm.volatility}
                onChange={(e) =>
                  setMarginForm({ ...marginForm, volatility: e.target.value })
                }
                step="0.5"
              />
            </div>
            <div>
              <label className="block text-sm text-zinc-500 mb-2">
                Instrument Type
              </label>
              <div className="flex gap-4">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    checked={marginForm.is_futures}
                    onChange={() =>
                      setMarginForm({ ...marginForm, is_futures: true })
                    }
                    className="accent-blue-500"
                  />
                  <span className="text-sm">Futures</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    checked={!marginForm.is_futures}
                    onChange={() =>
                      setMarginForm({ ...marginForm, is_futures: false })
                    }
                    className="accent-blue-500"
                  />
                  <span className="text-sm">Options</span>
                </label>
              </div>
            </div>
            <button onClick={calculateMargin} className="btn btn-primary w-full">
              Calculate Margin
            </button>

            {marginResult && (
              <div className="mt-4">
                <div className="p-4 bg-zinc-900 rounded-lg mb-4">
                  <span className="text-xs text-zinc-500 block mb-1">
                    Total Margin Required
                  </span>
                  <div className="text-2xl font-bold text-blue-500">
                    {formatCurrency(marginResult.total_margin)}
                  </div>
                  <span className="text-xs text-zinc-500">
                    Leverage: {marginResult.leverage}x
                  </span>
                </div>
                <div className="h-32">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={marginPieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={30}
                        outerRadius={50}
                        paddingAngle={5}
                        dataKey="value"
                      >
                        {marginPieData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{
                          background: "#1a1a1a",
                          border: "1px solid #262626",
                          borderRadius: "8px",
                        }}
                        formatter={(value) => formatCurrency(value)}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="flex justify-center gap-4 text-xs">
                  <span className="flex items-center gap-1">
                    <span className="w-3 h-3 bg-blue-500 rounded"></span>
                    SPAN ({marginResult.span_margin_pct}%)
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-3 h-3 bg-purple-500 rounded"></span>
                    Exposure ({marginResult.exposure_margin_pct}%)
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Risk Guidelines */}
      <div className="card mt-6 bg-blue-900/10 border-blue-900/30">
        <div className="flex items-start gap-3">
          <Shield className="w-5 h-5 text-blue-500 mt-0.5" />
          <div>
            <h3 className="font-medium text-blue-500 mb-1">
              Risk Management Guidelines
            </h3>
            <ul className="text-sm text-zinc-400 list-disc list-inside space-y-1">
              <li>Never risk more than 1-2% of capital per trade</li>
              <li>
                Maintain at least 2x margin buffer for F&O positions
              </li>
              <li>
                Monitor VaR daily and reduce positions if it exceeds comfort
                level
              </li>
              <li>
                Diversify across strategies - don't put all capital in one
                approach
              </li>
              <li>Set daily loss limits and stop trading when hit</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
