import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import { API } from "../App";
import {
  RefreshCw,
  ArrowUpDown,
  Zap,
  Clock,
  ChevronDown,
} from "lucide-react";
import { toast } from "sonner";

const REFRESH_INTERVAL = 5000;

function formatOI(val) {
  if (!val && val !== 0) return "—";
  if (val >= 10000000) return (val / 10000000).toFixed(2) + " Cr";
  if (val >= 100000) return (val / 100000).toFixed(2) + " L";
  if (val >= 1000) return (val / 1000).toFixed(1) + " K";
  return val.toLocaleString("en-IN");
}

function formatPrice(val) {
  if (!val && val !== 0) return "—";
  return val.toFixed(2);
}

function formatIV(val) {
  if (!val && val !== 0) return "—";
  return val.toFixed(1);
}

export default function OptionChain() {
  const [underlying, setUnderlying] = useState("NIFTY");
  const [expiry, setExpiry] = useState("");
  const [numStrikes, setNumStrikes] = useState(15);
  const [chain, setChain] = useState(null);
  const [expiries, setExpiries] = useState([]);
  const [underlyings, setUnderlyings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [fetchTime, setFetchTime] = useState(0);
  const intervalRef = useRef(null);
  const atmRef = useRef(null);

  useEffect(() => {
    axios.get(`${API}/options/underlyings`).then((r) => setUnderlyings(r.data)).catch(() => {});
  }, []);

  useEffect(() => {
    setExpiry("");
    setChain(null);
    axios
      .get(`${API}/options/expiries?underlying=${underlying}`)
      .then((r) => {
        setExpiries(r.data);
        if (r.data.length > 0) setExpiry(r.data[0].expiry);
      })
      .catch(() => setExpiries([]));
  }, [underlying]);

  const fetchChain = useCallback(async () => {
    if (!expiry) return;
    const start = Date.now();
    try {
      const res = await axios.get(
        `${API}/options/chain?underlying=${underlying}&expiry=${expiry}&num_strikes=${numStrikes}`,
        { timeout: 30000 }
      );
      setChain(res.data);
      setLastUpdate(new Date());
      setFetchTime(Date.now() - start);
    } catch (err) {
      console.error("Option chain fetch error:", err);
      if (!chain) toast.error("Failed to fetch option chain");
    } finally {
      setLoading(false);
    }
  }, [underlying, expiry, numStrikes]);

  useEffect(() => {
    if (!expiry) return;
    setLoading(true);
    fetchChain();
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (autoRefresh) {
      intervalRef.current = setInterval(fetchChain, REFRESH_INTERVAL);
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [fetchChain, autoRefresh, expiry]);

  useEffect(() => {
    if (chain && atmRef.current) {
      atmRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [chain?.atm_strike]);

  // Expiry label for display
  const expiryObj = expiries.find((e) => e.expiry === expiry);
  const expiryLabel = expiryObj ? `${expiryObj.expiry} (${expiryObj.date})` : expiry;

  if (loading && !chain) {
    return (
      <div className="page-container">
        <div className="flex flex-col items-center justify-center min-h-[400px]">
          <div className="loading-spinner mb-4"></div>
          <p className="text-zinc-400">Loading option chain...</p>
          <p className="text-xs text-zinc-500 mt-2">Fetching instrument data from Angel One</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container" data-testid="option-chain-page">
      {/* ===== Prominent Symbol & Expiry Banner ===== */}
      <div className="oc-banner" data-testid="oc-banner">
        <div className="oc-banner-left">
          <h1 className="oc-banner-symbol" data-testid="oc-current-symbol">{underlying}</h1>
          <span className="oc-banner-expiry" data-testid="oc-current-expiry">{expiryLabel}</span>
          {chain && (
            <span className="oc-banner-spot">
              Spot <span className="font-mono text-white">{chain.spot_price?.toLocaleString("en-IN")}</span>
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-[11px] sm:text-xs font-medium transition-colors ${
              autoRefresh
                ? "bg-green-900/20 border-green-900/50 text-green-500"
                : "bg-zinc-900 border-zinc-800 text-zinc-400"
            }`}
            data-testid="auto-refresh-toggle"
          >
            <Zap className="w-3 h-3 sm:w-3.5 sm:h-3.5" />
            {autoRefresh ? "Auto 5s" : "Paused"}
          </button>
          <button
            onClick={fetchChain}
            className="btn btn-secondary flex items-center gap-1 text-xs px-2 sm:px-4 py-1.5"
            data-testid="refresh-chain-btn"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Refresh</span>
          </button>
        </div>
      </div>

      {/* ===== Controls ===== */}
      <div className="oc-controls-row mb-3">
        <div className="oc-control-group">
          <label className="oc-control-label">Underlying</label>
          <select value={underlying} onChange={(e) => setUnderlying(e.target.value)} className="oc-select" data-testid="underlying-select">
            {underlyings.length > 0 ? (
              <>
                <optgroup label="Indices">
                  {underlyings.filter((u) => u.is_index).map((u) => (
                    <option key={u.name} value={u.name}>{u.name}</option>
                  ))}
                </optgroup>
                <optgroup label="Stocks">
                  {underlyings.filter((u) => !u.is_index).slice(0, 30).map((u) => (
                    <option key={u.name} value={u.name}>{u.name}</option>
                  ))}
                </optgroup>
              </>
            ) : (
              <option value="NIFTY">NIFTY</option>
            )}
          </select>
        </div>
        <div className="oc-control-group">
          <label className="oc-control-label">Expiry</label>
          <select value={expiry} onChange={(e) => setExpiry(e.target.value)} className="oc-select" data-testid="expiry-select">
            {expiries.map((e) => (
              <option key={e.expiry} value={e.expiry}>{e.expiry} ({e.date})</option>
            ))}
          </select>
        </div>
        <div className="oc-control-group">
          <label className="oc-control-label">Strikes</label>
          <select value={numStrikes} onChange={(e) => setNumStrikes(parseInt(e.target.value))} className="oc-select oc-select-sm" data-testid="strikes-select">
            <option value={10}>10</option>
            <option value={15}>15</option>
            <option value={20}>20</option>
            <option value={25}>25</option>
          </select>
        </div>

        {chain && (
          <div className="oc-stats-inline">
            <span>ATM: <span className="font-mono text-yellow-500 font-semibold">{chain.atm_strike}</span></span>
            <span>PCR: <span className={`font-mono font-semibold ${chain.totals?.pcr > 1 ? "text-green-500" : "text-red-500"}`}>{chain.totals?.pcr}</span></span>
            <span className="text-zinc-600 hidden sm:flex items-center gap-1">
              <Clock className="w-3 h-3" />{lastUpdate?.toLocaleTimeString()} ({fetchTime}ms)
            </span>
          </div>
        )}
      </div>

      {/* ===== Summary Bar ===== */}
      {chain?.totals && (
        <div className="grid grid-cols-3 sm:grid-cols-5 gap-2 sm:gap-3 mb-4">
          <div className="oc-summary-card" data-testid="total-ce-oi">
            <span className="oc-summary-label">Call OI</span>
            <span className="oc-summary-value text-green-400">{formatOI(chain.totals.ce_oi)}</span>
          </div>
          <div className="oc-summary-card" data-testid="total-pe-oi">
            <span className="oc-summary-label">Put OI</span>
            <span className="oc-summary-value text-red-400">{formatOI(chain.totals.pe_oi)}</span>
          </div>
          <div className="oc-summary-card" data-testid="pcr-value">
            <span className="oc-summary-label">PCR</span>
            <span className={`oc-summary-value ${chain.totals.pcr > 1 ? "text-green-400" : "text-red-400"}`}>
              {chain.totals.pcr}
            </span>
          </div>
          <div className="oc-summary-card hidden sm:block" data-testid="total-ce-vol">
            <span className="oc-summary-label">Call Vol</span>
            <span className="oc-summary-value text-green-300">{formatOI(chain.totals.ce_volume)}</span>
          </div>
          <div className="oc-summary-card hidden sm:block" data-testid="total-pe-vol">
            <span className="oc-summary-label">Put Vol</span>
            <span className="oc-summary-value text-red-300">{formatOI(chain.totals.pe_volume)}</span>
          </div>
        </div>
      )}

      {/* ===== T-Shaped Table (CE=Green, PE=Red) ===== */}
      {chain?.chain && (
        <div className="oc-table-container" data-testid="option-chain-table">
          <table className="oc-table">
            <thead>
              <tr>
                <th colSpan={6} className="oc-header-calls">CALLS (CE)</th>
                <th className="oc-header-strike">STRIKE</th>
                <th colSpan={6} className="oc-header-puts">PUTS (PE)</th>
              </tr>
              <tr>
                {["OI","Chg OI","Volume","IV","LTP","Chg"].map((col) => (
                  <th key={`ce-${col}`} className="oc-th-ce">{col}</th>
                ))}
                <th className="oc-th-strike"><ArrowUpDown className="w-3 h-3 inline mr-1" />Price</th>
                {["Chg","LTP","IV","Volume","Chg OI","OI"].map((col) => (
                  <th key={`pe-${col}`} className="oc-th-pe">{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {chain.chain.map((row) => {
                const isATM = row.is_atm;
                const itm_ce = row.is_itm_ce;
                const itm_pe = row.is_itm_pe;
                return (
                  <tr key={row.strike} ref={isATM ? atmRef : null} className={`oc-row ${isATM ? "oc-row-atm" : ""}`} data-testid={`strike-${row.strike}`}>
                    {/* CE — green tinted */}
                    <td className={`oc-td-ce ${itm_ce ? "oc-itm-ce" : ""}`}>{formatOI(row.ce?.oi)}</td>
                    <td className={`oc-td-ce ${itm_ce ? "oc-itm-ce" : ""} ${row.ce?.oi_change > 0 ? "text-green-400" : row.ce?.oi_change < 0 ? "text-red-400" : ""}`}>
                      {row.ce?.oi_change ? formatOI(row.ce.oi_change) : "—"}
                    </td>
                    <td className={`oc-td-ce ${itm_ce ? "oc-itm-ce" : ""}`}>{formatOI(row.ce?.volume)}</td>
                    <td className={`oc-td-ce ${itm_ce ? "oc-itm-ce" : ""}`}>{formatIV(row.ce?.iv)}</td>
                    <td className={`oc-td-ce oc-ltp-ce ${itm_ce ? "oc-itm-ce" : ""}`}>{formatPrice(row.ce?.ltp)}</td>
                    <td className={`oc-td-ce ${itm_ce ? "oc-itm-ce" : ""} ${row.ce?.change > 0 ? "text-green-400" : row.ce?.change < 0 ? "text-red-400" : ""}`}>
                      {row.ce?.change ? formatPrice(row.ce.change) : "—"}
                    </td>

                    {/* Strike */}
                    <td className={`oc-td-strike ${isATM ? "oc-atm-strike" : ""}`}>
                      {row.strike.toLocaleString("en-IN")}
                      {isATM && <span className="oc-atm-badge">ATM</span>}
                    </td>

                    {/* PE — red tinted */}
                    <td className={`oc-td-pe ${itm_pe ? "oc-itm-pe" : ""} ${row.pe?.change > 0 ? "text-green-400" : row.pe?.change < 0 ? "text-red-400" : ""}`}>
                      {row.pe?.change ? formatPrice(row.pe.change) : "—"}
                    </td>
                    <td className={`oc-td-pe oc-ltp-pe ${itm_pe ? "oc-itm-pe" : ""}`}>{formatPrice(row.pe?.ltp)}</td>
                    <td className={`oc-td-pe ${itm_pe ? "oc-itm-pe" : ""}`}>{formatIV(row.pe?.iv)}</td>
                    <td className={`oc-td-pe ${itm_pe ? "oc-itm-pe" : ""}`}>{formatOI(row.pe?.volume)}</td>
                    <td className={`oc-td-pe ${itm_pe ? "oc-itm-pe" : ""} ${row.pe?.oi_change > 0 ? "text-green-400" : row.pe?.oi_change < 0 ? "text-red-400" : ""}`}>
                      {row.pe?.oi_change ? formatOI(row.pe.oi_change) : "—"}
                    </td>
                    <td className={`oc-td-pe ${itm_pe ? "oc-itm-pe" : ""}`}>{formatOI(row.pe?.oi)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Footer */}
      {chain && (
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mt-3 text-[10px] sm:text-xs text-zinc-600 gap-1">
          <span>
            Source:{" "}
            <span className={chain.data_source === "angel_one_live" ? "text-green-500" : "text-yellow-500"}>
              {chain.data_source === "angel_one_live" ? "Angel One Live" : "No market data"}
            </span>
          </span>
          <span>
            {chain.chain?.length} strikes | Lot: {chain.chain?.[0]?.ce?.lot_size || chain.chain?.[0]?.pe?.lot_size || "—"}
          </span>
        </div>
      )}
    </div>
  );
}
