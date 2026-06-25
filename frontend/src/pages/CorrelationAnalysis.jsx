import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { API } from "../App";
import { Activity, RefreshCw, Download } from "lucide-react";
import { toast } from "sonner";

import CorrelationHeatmap from "../components/CorrelationHeatmap";
import CorrelationPairsList from "../components/CorrelationPairsList";
import CorrelationPairDetail from "../components/CorrelationPairDetail";

const TIMEFRAMES = [
  { value: 5, label: "5D" },
  { value: 10, label: "10D" },
  { value: 20, label: "20D" },
  { value: 60, label: "60D" },
  { value: 126, label: "6M" },
  { value: 252, label: "1Y" },
  { value: 504, label: "2Y" },
  { value: 756, label: "3Y" },
];

export default function CorrelationAnalysis() {
  const [timeframe, setTimeframe] = useState(20);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [matrixData, setMatrixData] = useState(null);
  const [pairsData, setPairsData] = useState(null);
  const [selectedPair, setSelectedPair] = useState(null);
  const [pairDetail, setPairDetail] = useState(null);
  const [pairLoading, setPairLoading] = useState(false);

  const symbols = matrixData?.symbols || [];
  const stockSectors = {};
  if (matrixData?.stocks) {
    for (const s of matrixData.stocks) {
      stockSectors[s.symbol] = s.sector;
    }
  }

  const fetchMatrix = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [matrixRes, pairsRes] = await Promise.all([
        axios.get(`${API}/correlation/matrix`, {
          params: { timeframe },
          timeout: 30000,
        }),
        axios.get(`${API}/correlation/pairs`, {
          params: { timeframe, min_corr: 0, limit: 50 },
          timeout: 30000,
        }),
      ]);
      setMatrixData(matrixRes.data);
      setPairsData(pairsRes.data);
    } catch (err) {
      console.error("Correlation fetch error:", err);
      setError(err.response?.data?.detail || err.message || "Failed to fetch data");
      toast.error("Failed to load correlation data. Check backend connection.");
    } finally {
      setLoading(false);
    }
  }, [timeframe]);

  useEffect(() => {
    fetchMatrix();
  }, [fetchMatrix]);

  const handleSelectPair = async (sym1, sym2) => {
    setSelectedPair({ sym1, sym2 });
    setPairLoading(true);
    setPairDetail(null);
    try {
      const res = await axios.get(`${API}/correlation/pair/${sym1}/${sym2}`, {
        params: { timeframe: Math.max(timeframe, 60) },
        timeout: 30000,
      });
      setPairDetail(res.data);
    } catch (err) {
      toast.error(`Failed to load pair analysis: ${err.message}`);
    } finally {
      setPairLoading(false);
    }
  };

  const handleClosePair = () => {
    setSelectedPair(null);
    setPairDetail(null);
  };

  const exportData = () => {
    if (!matrixData) return;
    const blob = new Blob([JSON.stringify(matrixData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `correlation_matrix_${timeframe}d_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Sector order for heatmap
  const sectorOrder = matrixData?.sectors?.order || [];

  return (
    <div className="page-container" data-testid="correlation-page">
      {/* Header */}
      <div className="page-header flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="page-title flex items-center gap-3">
            <Activity className="w-6 h-6 text-blue-500" />
            Correlation Analysis
          </h1>
          <p className="page-subtitle">
            Nifty 50 stock correlation matrix — find pairs, detect divergence, trade mean reversion
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchMatrix}
            disabled={loading}
            className="btn btn-secondary flex items-center gap-1.5 text-xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
          <button
            onClick={exportData}
            className="btn btn-secondary flex items-center gap-1.5 text-xs"
            disabled={!matrixData}
          >
            <Download className="w-3.5 h-3.5" />
            Export
          </button>
        </div>
      </div>

      {/* Timeframe selector */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <span className="text-xs text-zinc-500 font-semibold uppercase tracking-wider mr-1">
          Timeframe:
        </span>
        {TIMEFRAMES.map((tf) => (
          <button
            key={tf.value}
            onClick={() => {
              setTimeframe(tf.value);
              handleClosePair();
            }}
            className={`px-3 py-1.5 text-xs rounded-lg font-medium transition-all ${
              timeframe === tf.value
                ? "bg-blue-600 text-white shadow-lg shadow-blue-600/20"
                : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200"
            }`}
          >
            {tf.label}
          </button>
        ))}
        {loading && (
          <span className="text-xs text-blue-400 ml-2 animate-pulse">Loading...</span>
        )}
      </div>

      {/* Error state */}
      {error && (
        <div className="bg-red-900/20 border border-red-800/30 rounded-lg p-4 mb-4 text-sm text-red-400">
          {error}
          <button
            onClick={fetchMatrix}
            className="ml-3 underline hover:text-red-300"
          >
            Retry
          </button>
        </div>
      )}

      {/* Main layout */}
      <div className="grid grid-cols-1 xl:grid-cols-[1fr_300px] gap-4">
        {/* Left: Heatmap */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Correlation Matrix</span>
            {matrixData && (
              <span className="text-[10px] text-zinc-600">
                {matrixData.data_source === "nsepython_live" ? "Live NSE data" : "Simulated data"}
                {" · "}{symbols.length} stocks
              </span>
            )}
          </div>
          <CorrelationHeatmap
            symbols={symbols}
            stockSectors={stockSectors}
            matrix={matrixData?.matrix || []}
            sectorOrder={sectorOrder}
            onSelectPair={handleSelectPair}
            selectedPair={selectedPair}
          />
        </div>

        {/* Right: Pairs list */}
        <div className="card flex flex-col">
          <CorrelationPairsList
            pairs={pairsData?.pairs || []}
            onSelectPair={handleSelectPair}
            selectedPair={selectedPair}
            timeframeLabel={pairsData?.timeframe_label || ""}
            loading={loading}
          />
        </div>
      </div>

      {/* Pair detail (appears below the grid when selected) */}
      {pairLoading && (
        <div className="mt-4 bg-zinc-900/80 border border-zinc-700/50 rounded-xl p-8 flex items-center justify-center">
          <div className="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full mr-3" />
          <span className="text-sm text-zinc-400">
            Loading pair analysis...
          </span>
        </div>
      )}

      {pairDetail && !pairDetail.error && (
        <CorrelationPairDetail pair={pairDetail} onClose={handleClosePair} />
      )}

      {pairDetail?.error && (
        <div className="mt-4 bg-yellow-900/20 border border-yellow-800/30 rounded-lg p-4 text-sm text-yellow-400">
          {pairDetail.error}
        </div>
      )}

      {/* Info section */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-6">
        <div className="card bg-blue-900/10 border-blue-900/30">
          <h4 className="text-[10px] font-semibold text-blue-400 uppercase tracking-wider mb-1">
            How to use
          </h4>
          <p className="text-xs text-zinc-400">
            Hover over the heatmap to see individual correlations. Click a cell to analyze that pair's relationship in detail.
          </p>
        </div>
        <div className="card bg-green-900/10 border-green-900/30">
          <h4 className="text-[10px] font-semibold text-green-400 uppercase tracking-wider mb-1">
            Pairs Trading Signal
          </h4>
          <p className="text-xs text-zinc-400">
            When the price ratio deviates &gt;2σ from its mean, the spread is statistically overextended — potential mean reversion setup.
          </p>
        </div>
        <div className="card bg-purple-900/10 border-purple-900/30">
          <h4 className="text-[10px] font-semibold text-purple-400 uppercase tracking-wider mb-1">
            Sector Clusters
          </h4>
          <p className="text-xs text-zinc-400">
            Stocks are grouped by sector in the heatmap. Strong color blocks within a sector = high intra-sector correlation.
          </p>
        </div>
      </div>
    </div>
  );
}
