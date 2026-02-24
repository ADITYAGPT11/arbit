import { useState } from "react";
import axios from "axios";
import { API } from "../App";
import { GitCompare, CheckCircle, AlertCircle, Info } from "lucide-react";
import { toast } from "sonner";

export default function SyntheticArbitrage() {
  const [formData, setFormData] = useState({
    spot_price: "",
    call_price: "",
    put_price: "",
    strike: "",
    futures_price: "",
  });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const calculateArbitrage = async () => {
    const { spot_price, call_price, put_price, strike, futures_price } = formData;
    if (!spot_price || !call_price || !put_price || !strike || !futures_price) {
      toast.error("Please fill all required fields");
      return;
    }

    setLoading(true);
    try {
      const response = await axios.post(`${API}/arbitrage/synthetic`, null, {
        params: {
          spot_price: parseFloat(spot_price),
          call_price: parseFloat(call_price),
          put_price: parseFloat(put_price),
          strike: parseFloat(strike),
          futures_price: parseFloat(futures_price),
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
    <div className="page-container" data-testid="synthetic-page">
      <div className="page-header">
        <h1 className="page-title">Synthetic Futures Arbitrage</h1>
        <p className="page-subtitle">
          Compare synthetic futures (Call - Put + Strike) vs actual futures
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Input Form */}
        <div className="card" data-testid="synthetic-form">
          <div className="card-header">
            <span className="card-title">Input Parameters</span>
            <GitCompare className="w-4 h-4 text-zinc-500" />
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
                placeholder="e.g., 22000"
                value={formData.spot_price}
                onChange={handleChange}
                data-testid="spot-price-input"
              />
            </div>

            <div>
              <label className="block text-sm text-zinc-500 mb-2">
                ATM Strike Price (₹) *
              </label>
              <input
                type="number"
                name="strike"
                className="input"
                placeholder="e.g., 22000"
                value={formData.strike}
                onChange={handleChange}
                data-testid="strike-input"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-zinc-500 mb-2">
                  ATM Call Price (₹) *
                </label>
                <input
                  type="number"
                  name="call_price"
                  className="input"
                  placeholder="e.g., 250"
                  value={formData.call_price}
                  onChange={handleChange}
                  data-testid="call-price-input"
                />
              </div>
              <div>
                <label className="block text-sm text-zinc-500 mb-2">
                  ATM Put Price (₹) *
                </label>
                <input
                  type="number"
                  name="put_price"
                  className="input"
                  placeholder="e.g., 200"
                  value={formData.put_price}
                  onChange={handleChange}
                  data-testid="put-price-input"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm text-zinc-500 mb-2">
                Futures Price (₹) *
              </label>
              <input
                type="number"
                name="futures_price"
                className="input"
                placeholder="e.g., 22100"
                value={formData.futures_price}
                onChange={handleChange}
                data-testid="futures-price-input"
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
        <div className="card" data-testid="synthetic-result">
          <div className="card-header">
            <span className="card-title">Analysis Result</span>
            {result && (
              <span
                className={`badge ${
                  result.is_profitable ? "badge-green" : "badge-red"
                }`}
              >
                {result.is_profitable ? "Opportunity" : "No Opportunity"}
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
                    <AlertCircle className="w-5 h-5 text-yellow-500" />
                  )}
                  <span className="font-medium">Strategy</span>
                </div>
                <p className="text-sm text-zinc-400">{result.strategy}</p>
              </div>

              {/* Comparison */}
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 bg-blue-900/10 border border-blue-900/30 rounded-lg text-center">
                  <span className="text-xs text-zinc-500 block mb-1">
                    Synthetic Future
                  </span>
                  <span className="font-mono text-xl font-bold text-blue-500">
                    {formatPrice(result.synthetic_future)}
                  </span>
                  <span className="text-xs text-zinc-500 block mt-1">
                    Call - Put + Strike
                  </span>
                </div>
                <div className="p-4 bg-purple-900/10 border border-purple-900/30 rounded-lg text-center">
                  <span className="text-xs text-zinc-500 block mb-1">
                    Actual Future
                  </span>
                  <span className="font-mono text-xl font-bold text-purple-500">
                    {formatPrice(result.actual_future)}
                  </span>
                  <span className="text-xs text-zinc-500 block mt-1">
                    Market Price
                  </span>
                </div>
              </div>

              {/* Key Metrics */}
              <div className="data-grid">
                <div className="data-row">
                  <span className="data-label">Mispricing</span>
                  <span
                    className={`data-value ${
                      Math.abs(result.mispricing) > 0
                        ? "text-yellow-500"
                        : "text-zinc-500"
                    }`}
                  >
                    {formatPrice(result.mispricing)}
                  </span>
                </div>
                <div className="data-row">
                  <span className="data-label">Mispricing %</span>
                  <span
                    className={`data-value ${
                      Math.abs(result.mispricing_pct) > 0.1
                        ? "text-yellow-500"
                        : "text-zinc-500"
                    }`}
                  >
                    {result.mispricing_pct}%
                  </span>
                </div>
                <div className="data-row">
                  <span className="data-label">Transaction Cost</span>
                  <span className="data-value text-red-500">
                    {formatPrice(result.transaction_cost)}
                  </span>
                </div>
                <div className="data-row">
                  <span className="data-label">Net Profit</span>
                  <span
                    className={`data-value ${
                      result.net_profit > 0 ? "text-green-500" : "text-red-500"
                    }`}
                  >
                    {formatPrice(result.net_profit)}
                  </span>
                </div>
              </div>

              {/* Legs */}
              <div className="p-4 bg-zinc-900 rounded-lg">
                <h4 className="text-sm font-medium mb-3">Required Legs</h4>
                <div className="space-y-2 text-sm">
                  {result.mispricing > 0 ? (
                    <>
                      <div className="flex justify-between">
                        <span className="text-green-500">Buy ATM Call</span>
                        <span className="font-mono">{formatPrice(result.call_price)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-red-500">Sell ATM Put</span>
                        <span className="font-mono">{formatPrice(result.put_price)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-red-500">Sell Futures</span>
                        <span className="font-mono">{formatPrice(result.actual_future)}</span>
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="flex justify-between">
                        <span className="text-red-500">Sell ATM Call</span>
                        <span className="font-mono">{formatPrice(result.call_price)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-green-500">Buy ATM Put</span>
                        <span className="font-mono">{formatPrice(result.put_price)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-green-500">Buy Futures</span>
                        <span className="font-mono">{formatPrice(result.actual_future)}</span>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="empty-state">
              <GitCompare className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
              <p>Enter parameters and click Calculate</p>
            </div>
          )}
        </div>
      </div>

      {/* Info Box */}
      <div className="card mt-6 bg-blue-900/10 border-blue-900/30">
        <div className="flex items-start gap-3">
          <Info className="w-5 h-5 text-blue-500 mt-0.5" />
          <div>
            <h3 className="font-medium text-blue-500 mb-1">
              Synthetic Futures Explained
            </h3>
            <p className="text-sm text-zinc-400 mb-2">
              A synthetic future is created using put-call parity:
            </p>
            <p className="text-sm font-mono bg-zinc-900 p-2 rounded">
              Synthetic Future = ATM Call - ATM Put + Strike Price
            </p>
            <p className="text-sm text-zinc-400 mt-2">
              If the actual futures price differs significantly from the
              synthetic future, arbitrage opportunities exist. You can profit by
              trading the mispriced instrument against the fairly priced one.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
