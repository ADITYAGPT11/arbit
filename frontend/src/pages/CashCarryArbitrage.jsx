import { useState } from "react";
import axios from "axios";
import { API } from "../App";
import { Calculator, TrendingUp, AlertCircle, CheckCircle } from "lucide-react";
import { toast } from "sonner";

export default function CashCarryArbitrage() {
  const [formData, setFormData] = useState({
    spot_price: "",
    futures_price: "",
    days_to_expiry: "",
    risk_free_rate: "7.0",
  });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const calculateArbitrage = async () => {
    if (
      !formData.spot_price ||
      !formData.futures_price ||
      !formData.days_to_expiry
    ) {
      toast.error("Please fill all required fields");
      return;
    }

    setLoading(true);
    try {
      const response = await axios.post(`${API}/arbitrage/cash-carry`, null, {
        params: {
          spot_price: parseFloat(formData.spot_price),
          futures_price: parseFloat(formData.futures_price),
          days_to_expiry: parseInt(formData.days_to_expiry),
          risk_free_rate: parseFloat(formData.risk_free_rate),
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

  return (
    <div className="page-container" data-testid="cash-carry-page">
      <div className="page-header">
        <h1 className="page-title">Cash & Carry Arbitrage Calculator</h1>
        <p className="page-subtitle">
          Calculate Futures vs Spot mispricing for risk-free returns
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Input Form */}
        <div className="card" data-testid="cash-carry-form">
          <div className="card-header">
            <span className="card-title">Input Parameters</span>
            <Calculator className="w-4 h-4 text-zinc-500" />
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm text-zinc-500 mb-2">
                Spot Price (₹) *
              </label>
              <input
                type="number"
                name="spot_price"
                className="input"
                placeholder="e.g., 2500"
                value={formData.spot_price}
                onChange={handleChange}
                data-testid="spot-price-input"
              />
            </div>

            <div>
              <label className="block text-sm text-zinc-500 mb-2">
                Futures Price (₹) *
              </label>
              <input
                type="number"
                name="futures_price"
                className="input"
                placeholder="e.g., 2520"
                value={formData.futures_price}
                onChange={handleChange}
                data-testid="futures-price-input"
              />
            </div>

            <div>
              <label className="block text-sm text-zinc-500 mb-2">
                Days to Expiry *
              </label>
              <input
                type="number"
                name="days_to_expiry"
                className="input"
                placeholder="e.g., 15"
                value={formData.days_to_expiry}
                onChange={handleChange}
                data-testid="days-expiry-input"
              />
            </div>

            <div>
              <label className="block text-sm text-zinc-500 mb-2">
                Risk-Free Rate (%)
              </label>
              <input
                type="number"
                name="risk_free_rate"
                className="input"
                placeholder="7.0"
                value={formData.risk_free_rate}
                onChange={handleChange}
                step="0.1"
                data-testid="risk-rate-input"
              />
            </div>

            <button
              onClick={calculateArbitrage}
              className="btn btn-primary w-full"
              disabled={loading}
              data-testid="calculate-btn"
            >
              {loading ? "Calculating..." : "Calculate Arbitrage"}
            </button>
          </div>
        </div>

        {/* Results */}
        <div className="card" data-testid="cash-carry-result">
          <div className="card-header">
            <span className="card-title">Analysis Result</span>
            {result && (
              <span
                className={`badge ${
                  result.is_profitable ? "badge-green" : "badge-red"
                }`}
              >
                {result.is_profitable ? "Profitable" : "Not Profitable"}
              </span>
            )}
          </div>

          {result ? (
            <div className="space-y-4">
              {/* Strategy */}
              <div className="p-4 bg-zinc-900 rounded-lg border border-zinc-800">
                <div className="flex items-center gap-2 mb-2">
                  {result.is_profitable ? (
                    <CheckCircle className="w-5 h-5 text-green-500" />
                  ) : (
                    <AlertCircle className="w-5 h-5 text-red-500" />
                  )}
                  <span className="font-medium">Recommended Strategy</span>
                </div>
                <p className="text-sm text-zinc-400">{result.strategy}</p>
              </div>

              {/* Key Metrics */}
              <div className="grid grid-cols-2 gap-4">
                <div className="data-row">
                  <span className="data-label">Fair Value</span>
                  <span className="data-value">
                    {formatPrice(result.fair_value)}
                  </span>
                </div>
                <div className="data-row">
                  <span className="data-label">Mispricing</span>
                  <span
                    className={`data-value ${
                      result.mispricing > 0 ? "text-green-500" : "text-red-500"
                    }`}
                  >
                    {formatPrice(result.mispricing)}
                  </span>
                </div>
                <div className="data-row">
                  <span className="data-label">Basis</span>
                  <span className="data-value">{formatPrice(result.basis)}</span>
                </div>
                <div className="data-row">
                  <span className="data-label">Basis %</span>
                  <span className="data-value">{result.basis_pct}%</span>
                </div>
                <div className="data-row">
                  <span className="data-label">Annualized Basis</span>
                  <span className="data-value text-yellow-500">
                    {result.annualized_basis}%
                  </span>
                </div>
                <div className="data-row">
                  <span className="data-label">Transaction Cost</span>
                  <span className="data-value text-red-500">
                    {formatPrice(result.transaction_cost)}
                  </span>
                </div>
              </div>

              {/* Profit Metrics */}
              <div className="p-4 bg-green-900/10 border border-green-900/30 rounded-lg">
                <h4 className="text-sm font-medium text-green-500 mb-3">
                  Profit Analysis
                </h4>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <span className="text-xs text-zinc-500">Net Profit/Lot</span>
                    <div
                      className={`font-mono text-lg font-bold ${
                        result.net_profit > 0
                          ? "text-green-500"
                          : "text-red-500"
                      }`}
                    >
                      {formatPrice(result.net_profit)}
                    </div>
                  </div>
                  <div>
                    <span className="text-xs text-zinc-500">
                      Annualized Return
                    </span>
                    <div
                      className={`font-mono text-lg font-bold ${
                        result.annualized_return > 0
                          ? "text-green-500"
                          : "text-red-500"
                      }`}
                    >
                      {result.annualized_return}%
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="empty-state">
              <Calculator className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
              <p>Enter parameters and click Calculate</p>
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
              How Cash & Carry Arbitrage Works
            </h3>
            <p className="text-sm text-zinc-400 mb-2">
              When futures trade at a premium to spot price, you can:
            </p>
            <ol className="text-sm text-zinc-400 list-decimal list-inside space-y-1">
              <li>Buy the stock in cash market</li>
              <li>Sell equivalent futures</li>
              <li>
                Hold till expiry when futures converge to spot (basis = 0)
              </li>
              <li>
                Profit = Initial Basis - Transaction Costs - Funding Cost
              </li>
            </ol>
            <p className="text-sm text-zinc-400 mt-2">
              The annualized return shows what you'd earn if you could repeat
              this trade throughout the year.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
