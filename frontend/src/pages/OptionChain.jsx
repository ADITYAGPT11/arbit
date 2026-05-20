import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import { API } from "../App";
import {
  RefreshCw,
  ChevronDown,
  ArrowUpDown,
  Zap,
  Clock,
  TrendingUp,
  TrendingDown,
} from "lucide-react";
import { toast } from "sonner";

const REFRESH_INTERVAL = 5000; // 5 seconds

function formatNum(val, decimals = 2) {
  if (!val && val !== 0) return "—";
  if (val >= 10000000) return (val / 10000000).toFixed(2) + " Cr";
  if (val >= 100000) return (val / 100000).toFixed(2) + " L";
  if (val >= 1000) return (val / 1000).toFixed(1) + " K";
  return typeof val === "number" ? val.toFixed(decimals) : val;
}

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

  // Fetch underlyings list
  useEffect(() => {
    axios
      .get(`${API}/options/underlyings`)
      .then((res) => setUnderlyings(res.data))
      .catch(() => {});
  }, []);

  // Fetch expiries when underlying changes
  useEffect(() => {
    setExpiry("");
    setChain(null);
    axios
      .get(`${API}/options/expiries?underlying=${underlying}`)
      .then((res) => {
        setExpiries(res.data);
        if (res.data.length > 0) {
          setExpiry(res.data[0].expiry);
        }
      })
      .catch(() => setExpiries([]));
  }, [underlying]);

  // Fetch option chain
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

  // Initial fetch + auto-refresh
  useEffect(() => {
    if (!expiry) return;
    setLoading(true);
    fetchChain();

    if (intervalRef.current) clearInterval(intervalRef.current);
    if (autoRefresh) {
      intervalRef.current = setInterval(fetchChain, REFRESH_INTERVAL);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchChain, autoRefresh, expiry]);

  // Scroll to ATM on first load
  useEffect(() => {
    if (chain && atmRef.current) {
      atmRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [chain?.atm_strike]);

  const ceColumns = ["OI", "Chg OI", "Volume", "IV", "LTP", "Chg"];
  const peColumns = ["Chg", "LTP", "IV", "Volume", "Chg OI", "OI"];

  if (loading && !chain) {
    return (
      <div className="page-container">
        <div className="flex flex-col items-center justify-center min-h-[400px]">
          <div className="loading-spinner mb-4"></div>
          <p className="text-zinc-400">Loading option chain...</p>
          <p className="text-xs text-zinc-500 mt-2">
            Fetching instrument data from Angel One
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container" data-testid="option-chain-page">
      {/* Header */}
      <div className="flex flex-col gap-4 mb-5">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-2xl font-bold">Option Chain</h1>
            <p className="text-zinc-500 text-sm">
              T-shaped view with live data from Angel One
            </p>
          </div>
          <div className="flex items-center gap-3">
            {/* Auto-refresh toggle */}
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
                autoRefresh
                  ? "bg-green-900/20 border-green-900/50 text-green-500"
                  : "bg-zinc-900 border-zinc-800 text-zinc-400"
              }`}
              data-testid="auto-refresh-toggle"
            >
              <Zap className="w-3.5 h-3.5" />
              {autoRefresh ? "Auto 5s" : "Paused"}
            </button>
            <button
              onClick={fetchChain}
              className="btn btn-secondary flex items-center gap-2"
              data-testid="refresh-chain-btn"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh
            </button>
          </div>
        </div>

        {/* Controls Row */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Underlying select */}
          <div className="flex items-center gap-2">
            <label className="text-xs text-zinc-500 uppercase tracking-wide">
              Underlying
            </label>
            <select
              value={underlying}
              onChange={(e) => setUnderlying(e.target.value)}
              className="select bg-zinc-900 border-zinc-700 text-sm py-1.5 px-3 w-auto min-w-[140px]"
              data-testid="underlying-select"
            >
              {underlyings.length > 0 ? (
                <>
                  <optgroup label="Indices">
                    {underlyings
                      .filter((u) => u.is_index)
                      .map((u) => (
                        <option key={u.name} value={u.name}>
                          {u.name}
                        </option>
                      ))}
                  </optgroup>
                  <optgroup label="Stocks">
                    {underlyings
                      .filter((u) => !u.is_index)
                      .slice(0, 30)
                      .map((u) => (
                        <option key={u.name} value={u.name}>
                          {u.name}
                        </option>
                      ))}
                  </optgroup>
                </>
              ) : (
                <>
                  <option value="NIFTY">NIFTY</option>
                  <option value="BANKNIFTY">BANKNIFTY</option>
                  <option value="FINNIFTY">FINNIFTY</option>
                </>
              )}
            </select>
          </div>

          {/* Expiry select */}
          <div className="flex items-center gap-2">
            <label className="text-xs text-zinc-500 uppercase tracking-wide">
              Expiry
            </label>
            <select
              value={expiry}
              onChange={(e) => setExpiry(e.target.value)}
              className="select bg-zinc-900 border-zinc-700 text-sm py-1.5 px-3 w-auto min-w-[140px]"
              data-testid="expiry-select"
            >
              {expiries.map((e) => (
                <option key={e.expiry} value={e.expiry}>
                  {e.expiry} ({e.date})
                </option>
              ))}
            </select>
          </div>

          {/* Strikes */}
          <div className="flex items-center gap-2">
            <label className="text-xs text-zinc-500 uppercase tracking-wide">
              Strikes
            </label>
            <select
              value={numStrikes}
              onChange={(e) => setNumStrikes(parseInt(e.target.value))}
              className="select bg-zinc-900 border-zinc-700 text-sm py-1.5 px-3 w-auto"
              data-testid="strikes-select"
            >
              <option value={10}>10</option>
              <option value={15}>15</option>
              <option value={20}>20</option>
              <option value={25}>25</option>
            </select>
          </div>

          {/* Status indicators */}
          {chain && (
            <div className="flex items-center gap-4 ml-auto text-xs">
              <span className="text-zinc-500">
                Spot:{" "}
                <span className="font-mono text-white font-medium">
                  {chain.spot_price?.toLocaleString("en-IN")}
                </span>
              </span>
              <span className="text-zinc-500">
                ATM:{" "}
                <span className="font-mono text-yellow-500 font-medium">
                  {chain.atm_strike}
                </span>
              </span>
              <span className="text-zinc-500">
                PCR:{" "}
                <span
                  className={`font-mono font-medium ${
                    chain.totals?.pcr > 1
                      ? "text-green-500"
                      : "text-red-500"
                  }`}
                >
                  {chain.totals?.pcr}
                </span>
              </span>
              <span className="text-zinc-600 flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {lastUpdate?.toLocaleTimeString()} ({fetchTime}ms)
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Summary Bar */}
      {chain?.totals && (
        <div className="grid grid-cols-5 gap-3 mb-4">
          <div className="oc-summary-card" data-testid="total-ce-oi">
            <span className="oc-summary-label">Total Call OI</span>
            <span className="oc-summary-value text-red-400">
              {formatOI(chain.totals.ce_oi)}
            </span>
          </div>
          <div className="oc-summary-card" data-testid="total-pe-oi">
            <span className="oc-summary-label">Total Put OI</span>
            <span className="oc-summary-value text-green-400">
              {formatOI(chain.totals.pe_oi)}
            </span>
          </div>
          <div className="oc-summary-card" data-testid="pcr-value">
            <span className="oc-summary-label">PCR (OI)</span>
            <span
              className={`oc-summary-value ${
                chain.totals.pcr > 1 ? "text-green-400" : "text-red-400"
              }`}
            >
              {chain.totals.pcr}
            </span>
          </div>
          <div className="oc-summary-card" data-testid="total-ce-vol">
            <span className="oc-summary-label">Call Volume</span>
            <span className="oc-summary-value text-zinc-300">
              {formatOI(chain.totals.ce_volume)}
            </span>
          </div>
          <div className="oc-summary-card" data-testid="total-pe-vol">
            <span className="oc-summary-label">Put Volume</span>
            <span className="oc-summary-value text-zinc-300">
              {formatOI(chain.totals.pe_volume)}
            </span>
          </div>
        </div>
      )}

      {/* T-Shaped Option Chain Table */}
      {chain?.chain && (
        <div className="oc-table-container" data-testid="option-chain-table">
          <table className="oc-table">
            <thead>
              <tr>
                <th colSpan={6} className="oc-header-calls">
                  CALLS (CE)
                </th>
                <th className="oc-header-strike">STRIKE</th>
                <th colSpan={6} className="oc-header-puts">
                  PUTS (PE)
                </th>
              </tr>
              <tr>
                {ceColumns.map((col) => (
                  <th key={`ce-${col}`} className="oc-th-ce">
                    {col}
                  </th>
                ))}
                <th className="oc-th-strike">
                  <ArrowUpDown className="w-3 h-3 inline mr-1" />
                  Price
                </th>
                {peColumns.map((col) => (
                  <th key={`pe-${col}`} className="oc-th-pe">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {chain.chain.map((row) => {
                const isATM = row.is_atm;
                const isITMce = row.is_itm_ce;
                const isITMpe = row.is_itm_pe;

                return (
                  <tr
                    key={row.strike}
                    ref={isATM ? atmRef : null}
                    className={`oc-row ${isATM ? "oc-row-atm" : ""}`}
                    data-testid={`strike-${row.strike}`}
                  >
                    {/* CE side */}
                    <td
                      className={`oc-td-ce ${isITMce ? "oc-itm" : ""}`}
                    >
                      {formatOI(row.ce?.oi)}
                    </td>
                    <td
                      className={`oc-td-ce ${isITMce ? "oc-itm" : ""} ${
                        row.ce?.oi_change > 0
                          ? "text-green-400"
                          : row.ce?.oi_change < 0
                          ? "text-red-400"
                          : ""
                      }`}
                    >
                      {row.ce?.oi_change ? formatOI(row.ce.oi_change) : "—"}
                    </td>
                    <td
                      className={`oc-td-ce ${isITMce ? "oc-itm" : ""}`}
                    >
                      {formatOI(row.ce?.volume)}
                    </td>
                    <td
                      className={`oc-td-ce ${isITMce ? "oc-itm" : ""}`}
                    >
                      {row.ce?.iv ? formatNum(row.ce.iv, 1) : "—"}
                    </td>
                    <td
                      className={`oc-td-ce oc-ltp ${
                        isITMce ? "oc-itm" : ""
                      }`}
                    >
                      {formatPrice(row.ce?.ltp)}
                    </td>
                    <td
                      className={`oc-td-ce ${isITMce ? "oc-itm" : ""} ${
                        row.ce?.change > 0
                          ? "text-green-400"
                          : row.ce?.change < 0
                          ? "text-red-400"
                          : ""
                      }`}
                    >
                      {row.ce?.change ? formatPrice(row.ce.change) : "—"}
                    </td>

                    {/* Strike */}
                    <td className={`oc-td-strike ${isATM ? "oc-atm-strike" : ""}`}>
                      {row.strike.toLocaleString("en-IN")}
                      {isATM && (
                        <span className="oc-atm-badge">ATM</span>
                      )}
                    </td>

                    {/* PE side */}
                    <td
                      className={`oc-td-pe ${isITMpe ? "oc-itm" : ""} ${
                        row.pe?.change > 0
                          ? "text-green-400"
                          : row.pe?.change < 0
                          ? "text-red-400"
                          : ""
                      }`}
                    >
                      {row.pe?.change ? formatPrice(row.pe.change) : "—"}
                    </td>
                    <td
                      className={`oc-td-pe oc-ltp ${
                        isITMpe ? "oc-itm" : ""
                      }`}
                    >
                      {formatPrice(row.pe?.ltp)}
                    </td>
                    <td
                      className={`oc-td-pe ${isITMpe ? "oc-itm" : ""}`}
                    >
                      {row.pe?.iv ? formatNum(row.pe.iv, 1) : "—"}
                    </td>
                    <td
                      className={`oc-td-pe ${isITMpe ? "oc-itm" : ""}`}
                    >
                      {formatOI(row.pe?.volume)}
                    </td>
                    <td
                      className={`oc-td-pe ${isITMpe ? "oc-itm" : ""} ${
                        row.pe?.oi_change > 0
                          ? "text-green-400"
                          : row.pe?.oi_change < 0
                          ? "text-red-400"
                          : ""
                      }`}
                    >
                      {row.pe?.oi_change ? formatOI(row.pe.oi_change) : "—"}
                    </td>
                    <td
                      className={`oc-td-pe ${isITMpe ? "oc-itm" : ""}`}
                    >
                      {formatOI(row.pe?.oi)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Data source info */}
      {chain && (
        <div className="flex items-center justify-between mt-3 text-xs text-zinc-600">
          <span>
            Data source:{" "}
            <span
              className={
                chain.data_source === "angel_one_live"
                  ? "text-green-500"
                  : "text-yellow-500"
              }
            >
              {chain.data_source === "angel_one_live"
                ? "Angel One Live"
                : "No market data (market closed)"}
            </span>
          </span>
          <span>
            {chain.chain?.length} strikes | Lot size:{" "}
            {chain.chain?.[0]?.ce?.lot_size || chain.chain?.[0]?.pe?.lot_size || "—"}
          </span>
        </div>
      )}
    </div>
  );
}
