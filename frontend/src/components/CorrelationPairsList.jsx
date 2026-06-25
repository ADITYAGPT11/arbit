import { useState, useMemo } from "react";
import { ArrowUpDown, TrendingUp, TrendingDown, Minus } from "lucide-react";

const SECTOR_COLORS = {
  Financial_Services: "#3b82f6",
  IT: "#8b5cf6",
  Oil_Gas: "#f59e0b",
  FMCG: "#10b981",
  Auto: "#ef4444",
  Pharma: "#06b6d4",
  Metals: "#f97316",
  Power: "#14b8a6",
  Telecom: "#ec4899",
  Construction: "#6366f1",
  Consumer: "#eab308",
  Healthcare: "#84cc16",
  Media: "#a855f7",
};

export default function CorrelationPairsList({
  pairs = [],
  onSelectPair,
  selectedPair,
  timeframeLabel,
  loading,
}) {
  const [sortBy, setSortBy] = useState("abs_corr");
  const [sortDir, setSortDir] = useState("desc");
  const [filter, setFilter] = useState("all");

  const filteredPairs = useMemo(() => {
    let result = [...pairs];

    if (filter === "same_sector") {
      result = result.filter((p) => p.same_sector);
    } else if (filter === "cross_sector") {
      result = result.filter((p) => !p.same_sector);
    }

    result.sort((a, b) => {
      const aVal = a[sortBy] || 0;
      const bVal = b[sortBy] || 0;
      return sortDir === "desc" ? bVal - aVal : aVal - bVal;
    });

    return result;
  }, [pairs, sortBy, sortDir, filter]);

  const toggleSort = (field) => {
    if (sortBy === field) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortBy(field);
      setSortDir("desc");
    }
  };

  const getSignalIcon = (corr, pair) => {
    if (pair.z_score !== undefined) {
      if (Math.abs(pair.z_score) > 2) {
        return pair.z_score > 0 ? (
          <TrendingUp className="w-3 h-3 text-red-400" />
        ) : (
          <TrendingDown className="w-3 h-3 text-green-400" />
        );
      }
    }
    if (corr > 0.8) return <TrendingUp className="w-3 h-3 text-green-500" />;
    if (corr < 0.3) return <TrendingDown className="w-3 h-3 text-red-500" />;
    return <Minus className="w-3 h-3 text-zinc-500" />;
  };

  // Group by sector if requested
  const groupedPairs = useMemo(() => {
    if (filter === "same_sector") {
      const groups = {};
      for (const p of filteredPairs) {
        const sec = p.sym1_sector || "Other";
        if (!groups[sec]) groups[sec] = [];
        groups[sec].push(p);
      }
      return groups;
    }
    return null;
  }, [filteredPairs, filter]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
          Top Pairs
        </h3>
        <span className="text-[10px] text-zinc-600">{timeframeLabel}</span>
      </div>

      {/* Filters */}
      <div className="flex gap-1.5 mb-3">
        {[
          { value: "all", label: "All" },
          { value: "same_sector", label: "Same Sector" },
          { value: "cross_sector", label: "Cross Sector" },
        ].map((f) => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className={`text-[10px] px-2 py-1 rounded transition-colors ${
              filter === f.value
                ? "bg-blue-600 text-white"
                : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Column headers */}
      <div className="grid grid-cols-[1fr_auto] gap-2 text-[9px] text-zinc-600 uppercase tracking-wider px-2 pb-1 border-b border-zinc-800">
        <span>Pair</span>
        <button
          onClick={() => toggleSort("abs_corr")}
          className="flex items-center gap-0.5 hover:text-zinc-400"
        >
          Corr
          <ArrowUpDown className="w-2.5 h-2.5" />
        </button>
      </div>

      {/* Pairs list */}
      <div className="flex-1 overflow-y-auto space-y-0.5 mt-1">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full" />
          </div>
        ) : filteredPairs.length === 0 ? (
          <div className="flex items-center justify-center py-8 text-zinc-600 text-xs">
            No pairs match filters
          </div>
        ) : groupedPairs ? (
          // Grouped view (same sector pairs)
          Object.entries(groupedPairs).map(([sector, sectorPairs]) => (
            <div key={sector} className="mb-2">
              <div
                className="text-[9px] px-2 py-1 font-semibold uppercase tracking-wider flex items-center gap-1"
                style={{ color: SECTOR_COLORS[sector] || "#666" }}
              >
                <span
                  className="w-1.5 h-1.5 rounded-full"
                  style={{ background: SECTOR_COLORS[sector] || "#666" }}
                />
                {sector.replace(/_/g, " ")} ({sectorPairs.length})
              </div>
              {sectorPairs.map((pair, idx) => (
                <PairRow
                  key={`${pair.sym1}-${pair.sym2}-${idx}`}
                  pair={pair}
                  isSelected={
                    selectedPair &&
                    ((selectedPair.sym1 === pair.sym1 && selectedPair.sym2 === pair.sym2) ||
                      (selectedPair.sym1 === pair.sym2 && selectedPair.sym2 === pair.sym1))
                  }
                  onClick={() => onSelectPair(pair.sym1, pair.sym2)}
                />
              ))}
            </div>
          ))
        ) : (
          // Flat list view
          filteredPairs.map((pair, idx) => (
            <PairRow
              key={`${pair.sym1}-${pair.sym2}-${idx}`}
              pair={pair}
              isSelected={
                selectedPair &&
                ((selectedPair.sym1 === pair.sym1 && selectedPair.sym2 === pair.sym2) ||
                  (selectedPair.sym1 === pair.sym2 && selectedPair.sym2 === pair.sym1))
              }
              onClick={() => onSelectPair(pair.sym1, pair.sym2)}
            />
          ))
        )}
      </div>

      <div className="text-[9px] text-zinc-700 pt-2 text-center border-t border-zinc-800 mt-2">
        {filteredPairs.length} pairs · click to analyze
      </div>
    </div>
  );
}

function PairRow({ pair, isSelected, onClick }) {
  const corr = pair.correlation || 0;
  const absCorr = Math.abs(corr);
  const barWidth = absCorr * 100;
  const barColor = corr > 0 ? "#22c55e" : "#ef4444";

  return (
    <div
      onClick={onClick}
      className={`
        grid grid-cols-[1fr_auto] gap-2 items-center px-2 py-1.5 rounded
        cursor-pointer transition-colors text-xs
        ${isSelected ? "bg-blue-600/20 ring-1 ring-blue-500/40" : "hover:bg-zinc-800/50"}
      `}
    >
      <div className="flex items-center gap-1.5 min-w-0">
        <span className="font-mono text-[11px] truncate">
          {pair.sym1}
        </span>
        <span className="text-zinc-600 text-[9px]">/</span>
        <span className="font-mono text-[11px] truncate">
          {pair.sym2}
        </span>
        {pair.same_sector && (
          <span className="text-[8px] px-1 rounded bg-zinc-800 text-zinc-500 flex-shrink-0">
            same
          </span>
        )}
      </div>

      <div className="flex items-center gap-1.5">
        <div className="w-12 h-1.5 bg-zinc-800 rounded-full overflow-hidden hidden sm:block">
          <div
            className="h-full rounded-full transition-all"
            style={{
              width: `${barWidth}%`,
              background: barColor,
            }}
          />
        </div>
        <span
          className={`font-mono text-[11px] w-10 text-right ${
            corr > 0.7
              ? "text-green-400"
              : corr < -0.3
              ? "text-red-400"
              : "text-zinc-400"
          }`}
        >
          {corr >= 0 ? "+" : ""}
          {(corr * 100).toFixed(0)}
        </span>
        {getSignalIcon(corr, pair)}
      </div>
    </div>
  );
}


