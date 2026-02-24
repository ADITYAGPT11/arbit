import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { API } from "../App";
import { RefreshCw, Search, AlertTriangle, TrendingUp } from "lucide-react";
import { toast } from "sonner";

export default function ArbitrageScanner() {
  const [opportunities, setOpportunities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchSymbols, setSearchSymbols] = useState("");
  const [minSpread, setMinSpread] = useState(0.1);

  const fetchArbitrage = useCallback(async () => {
    setLoading(true);
    try {
      const params = searchSymbols ? { symbols: searchSymbols } : {};
      const response = await axios.get(`${API}/arbitrage/cross-exchange`, {
        params,
      });
      setOpportunities(response.data);
    } catch (error) {
      console.error("Error fetching arbitrage:", error);
      toast.error("Failed to fetch arbitrage data");
    } finally {
      setLoading(false);
    }
  }, [searchSymbols]);

  useEffect(() => {
    fetchArbitrage();
    const interval = setInterval(fetchArbitrage, 15000);
    return () => clearInterval(interval);
  }, [fetchArbitrage]);

  const filteredOpps = opportunities.filter(
    (opp) => opp.spread_pct >= minSpread
  );

  const formatPrice = (price) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      minimumFractionDigits: 2,
    }).format(price);
  };

  return (
    <div className="page-container" data-testid="arbitrage-scanner">
      <div className="page-header">
        <h1 className="page-title">Cross-Exchange Arbitrage Scanner</h1>
        <p className="page-subtitle">
          Detect NSE vs BSE price differences for dual-listed stocks
        </p>
      </div>

      {/* Controls */}
      <div className="card mb-6">
        <div className="flex flex-wrap gap-4 items-end">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm text-zinc-500 mb-2">
              Search Symbols (comma-separated)
            </label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
              <input
                type="text"
                className="input pl-10"
                placeholder="e.g., RELIANCE, TCS, INFY"
                value={searchSymbols}
                onChange={(e) => setSearchSymbols(e.target.value.toUpperCase())}
                data-testid="symbol-search"
              />
            </div>
          </div>
          <div className="w-40">
            <label className="block text-sm text-zinc-500 mb-2">
              Min Spread %
            </label>
            <input
              type="number"
              className="input"
              value={minSpread}
              onChange={(e) => setMinSpread(parseFloat(e.target.value) || 0)}
              step="0.01"
              min="0"
              data-testid="min-spread"
            />
          </div>
          <button
            onClick={fetchArbitrage}
            className="btn btn-primary flex items-center gap-2"
            disabled={loading}
            data-testid="scan-btn"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            Scan Now
          </button>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="stat-card">
          <div className="stat-label">Total Opportunities</div>
          <div className="stat-value">{filteredOpps.length}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Highest Spread</div>
          <div className="stat-value text-green-500">
            {filteredOpps.length > 0
              ? `${filteredOpps[0].spread_pct.toFixed(2)}%`
              : "—"}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Avg Spread</div>
          <div className="stat-value">
            {filteredOpps.length > 0
              ? `${(
                  filteredOpps.reduce((a, b) => a + b.spread_pct, 0) /
                  filteredOpps.length
                ).toFixed(2)}%`
              : "—"}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Best Net Profit</div>
          <div className="stat-value text-green-500">
            {filteredOpps.length > 0
              ? formatPrice(
                  Math.max(...filteredOpps.map((o) => o.net_profit_per_share))
                )
              : "—"}
          </div>
        </div>
      </div>

      {/* Results Table */}
      <div className="card" data-testid="arbitrage-results">
        <div className="card-header">
          <span className="card-title">Detected Opportunities</span>
          <span className="badge badge-blue">{filteredOpps.length} found</span>
        </div>

        {loading ? (
          <div className="loading-container">
            <div className="loading-spinner"></div>
          </div>
        ) : filteredOpps.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>NSE Price</th>
                  <th>BSE Price</th>
                  <th>Spread</th>
                  <th>Spread %</th>
                  <th>Action</th>
                  <th>Net Profit/Share</th>
                  <th>Net Profit %</th>
                </tr>
              </thead>
              <tbody>
                {filteredOpps.map((opp, idx) => (
                  <tr key={idx}>
                    <td className="font-medium">{opp.symbol}</td>
                    <td
                      className={
                        opp.buy_exchange === "NSE" ? "text-green-500" : ""
                      }
                    >
                      {formatPrice(opp.nse_price)}
                    </td>
                    <td
                      className={
                        opp.buy_exchange === "BSE" ? "text-green-500" : ""
                      }
                    >
                      {formatPrice(opp.bse_price)}
                    </td>
                    <td>{formatPrice(opp.spread)}</td>
                    <td className="text-yellow-500">
                      {opp.spread_pct.toFixed(3)}%
                    </td>
                    <td>
                      <div className="text-xs">
                        <span className="text-green-500">
                          Buy {opp.buy_exchange}
                        </span>
                        <span className="text-zinc-500 mx-1">→</span>
                        <span className="text-red-500">
                          Sell {opp.sell_exchange}
                        </span>
                      </div>
                    </td>
                    <td
                      className={
                        opp.net_profit_per_share > 0
                          ? "text-green-500"
                          : "text-red-500"
                      }
                    >
                      {formatPrice(opp.net_profit_per_share)}
                    </td>
                    <td
                      className={
                        opp.net_profit_pct > 0
                          ? "text-green-500"
                          : "text-red-500"
                      }
                    >
                      {opp.net_profit_pct.toFixed(3)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">
            <AlertTriangle className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
            <p>No arbitrage opportunities found above {minSpread}% spread</p>
            <p className="text-xs mt-2">
              Try lowering the minimum spread threshold or searching different
              symbols
            </p>
          </div>
        )}
      </div>

      {/* Info Box */}
      <div className="card mt-6 bg-blue-900/10 border-blue-900/30">
        <div className="flex items-start gap-3">
          <TrendingUp className="w-5 h-5 text-blue-500 mt-0.5" />
          <div>
            <h3 className="font-medium text-blue-500 mb-1">
              How Cross-Exchange Arbitrage Works
            </h3>
            <p className="text-sm text-zinc-400">
              When the same stock trades at different prices on NSE and BSE, you
              can buy on the cheaper exchange and sell on the expensive one.
              After accounting for transaction costs (brokerage, STT, stamp
              duty), if there's still profit, it's an arbitrage opportunity. The
              net profit shown is after deducting all costs.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
