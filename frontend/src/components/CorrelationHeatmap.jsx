import { useState } from "react";
import { ZoomIn, ZoomOut, Info } from "lucide-react";

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

function getCorrColor(value) {
  if (value === null || value === undefined) return "#1a1a1a";
  const v = Math.max(-1, Math.min(1, value));
  if (v > 0) {
    const intensity = Math.round(v * 200);
    return `rgb(${intensity + 40}, ${40 + Math.round((1 - v) * 60)}, ${80 - Math.round(v * 40)})`;
  }
  const intensity = Math.round(Math.abs(v) * 150);
  return `rgb(${40}, ${40 + Math.round((1 - Math.abs(v)) * 40)}, ${intensity + 60})`;
}

function formatCorr(v) {
  if (v === null || v === undefined) return "—";
  const sign = v >= 0 ? "+" : "";
  return `${sign}${(v * 100).toFixed(0)}`;
}

function getStrengthLabel(v) {
  const abs = Math.abs(v);
  if (abs >= 0.8) return "Very Strong";
  if (abs >= 0.6) return "Strong";
  if (abs >= 0.4) return "Moderate";
  if (abs >= 0.2) return "Weak";
  return "None / Very Weak";
}

export default function CorrelationHeatmap({
  symbols = [],
  stockSectors = {},
  matrix = [],
  sectorOrder = [],
  onSelectPair,
  selectedPair,
}) {
  const [hoveredCell, setHoveredCell] = useState(null);
  const [zoom, setZoom] = useState(1);
  const [showGuide, setShowGuide] = useState(false);

  if (!symbols.length || !matrix.length) {
    return (
      <div className="flex items-center justify-center h-64 text-zinc-500 text-sm">
        No correlation data available
      </div>
    );
  }

  // Group symbols by sector for the heatmap
  const sectorGroups = [];
  const sectorSet = new Set();
  for (const sym of symbols) {
    const sec = stockSectors[sym] || "Unknown";
    if (!sectorSet.has(sec)) {
      sectorSet.add(sec);
      sectorGroups.push({ sector: sec, symbols: [sym] });
    } else {
      const group = sectorGroups.find((g) => g.sector === sec);
      if (group) group.symbols.push(sym);
    }
  }

  const cellSize = Math.max(10, Math.min(16, 640 / symbols.length));

  const matrixDim = symbols.length;

  const hoverInfo = hoveredCell
    ? {
        sym1: symbols[hoveredCell.row],
        sym2: symbols[hoveredCell.col],
        value: matrix[hoveredCell.row]?.[hoveredCell.col],
      }
    : null;

  const handleCellClick = (row, col) => {
    if (row !== col && onSelectPair) {
      onSelectPair(symbols[row], symbols[col]);
    }
  };

  return (
    <div className="space-y-3">
      {/* Controls */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {/* Zoom controls */}
          <div className="flex items-center gap-1 bg-zinc-800/50 rounded-lg px-1.5 py-1">
            <button
              onClick={() => setZoom((z) => Math.max(0.5, z - 0.2))}
              className="p-0.5 rounded hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200"
              title="Zoom out"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <span className="text-[10px] text-zinc-500 w-10 text-center font-mono">
              {Math.round(zoom * 100)}%
            </span>
            <button
              onClick={() => setZoom((z) => Math.min(2, z + 0.2))}
              className="p-0.5 rounded hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200"
              title="Zoom in"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Guide button */}
          <button
            onClick={() => setShowGuide(!showGuide)}
            className="flex items-center gap-1 text-[10px] text-zinc-500 hover:text-zinc-300 bg-zinc-800/50 rounded-lg px-2 py-1"
          >
            <Info className="w-3 h-3" />
            {showGuide ? "Hide guide" : "Guide"}
          </button>
        </div>

        {/* Hover info */}
        <div className="text-xs text-zinc-400 font-mono min-h-[18px]">
          {hoverInfo && (
            <span>
              <span style={{ color: SECTOR_COLORS[stockSectors[hoverInfo.sym1]] || "#666" }}>
                {hoverInfo.sym1}
              </span>
              {" / "}
              <span style={{ color: SECTOR_COLORS[stockSectors[hoverInfo.sym2]] || "#666" }}>
                {hoverInfo.sym2}
              </span>
              {": "}
              <span className={hoverInfo.value >= 0 ? "text-green-400" : "text-red-400"}>
                {formatCorr(hoverInfo.value)}
              </span>
              <span className="text-zinc-600 text-[10px] ml-1">
                ({getStrengthLabel(hoverInfo.value)})
              </span>
            </span>
          )}
        </div>

        {/* Color legend */}
        <div className="flex items-center gap-1.5 text-[9px] text-zinc-500">
          <span>-1</span>
          <div className="flex h-2 w-20 sm:w-24 rounded overflow-hidden">
            <div className="flex-1" style={{ background: "#282845" }} />
            <div className="flex-1" style={{ background: "#1a1a2e" }} />
            <div className="flex-1" style={{ background: "#2a1a1a" }} />
            <div className="flex-1" style={{ background: "#3b2020" }} />
            <div className="flex-1" style={{ background: "#5a2020" }} />
            <div className="flex-1" style={{ background: "#8b2020" }} />
          </div>
          <span>+1</span>
        </div>
      </div>

      {/* Quick guide popup */}
      {showGuide && (
        <div className="bg-zinc-900 border border-zinc-700/50 rounded-lg p-3 text-xs text-zinc-400 space-y-2">
          <p><strong className="text-zinc-300">What is correlation?</strong> A measure of how two stocks move relative to each other, from -1 to +1.</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <div className="flex items-start gap-2">
              <div className="w-3 h-3 rounded mt-0.5 flex-shrink-0" style={{ background: "#8b2020" }} />
              <div>
                <span className="text-green-400 font-medium">+0.7 to +1.0</span>
                <p className="text-zinc-500">Strong positive — stocks move in the same direction</p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <div className="w-3 h-3 rounded mt-0.5 flex-shrink-0" style={{ background: "#282845" }} />
              <div>
                <span className="text-red-400 font-medium">-0.7 to -1.0</span>
                <p className="text-zinc-500">Strong negative — stocks move in opposite directions</p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <div className="w-3 h-3 rounded mt-0.5 flex-shrink-0" style={{ background: "#5a2020" }} />
              <div>
                <span className="text-yellow-400 font-medium">+0.3 to +0.7</span>
                <p className="text-zinc-500">Moderate — some tendency to move together</p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <div className="w-3 h-3 rounded mt-0.5 flex-shrink-0" style={{ background: "#1a1a2e" }} />
              <div>
                <span className="text-zinc-400 font-medium">-0.3 to +0.3</span>
                <p className="text-zinc-500">Weak — little to no relationship</p>
              </div>
            </div>
          </div>
          <p className="text-zinc-600 pt-1 border-t border-zinc-800">Click any cell (except diagonal) to analyze that pair in detail.</p>
        </div>
      )}

      {/* Heatmap container */}
      <div
        className="overflow-auto border border-zinc-800 rounded-lg bg-zinc-900/50"
        style={{ maxHeight: "75vh" }}
      >
        <div
          className="relative"
          style={{
            transform: `scale(${zoom})`,
            transformOrigin: "top left",
            minWidth: matrixDim * cellSize + 120,
          }}
        >
          {/* Y-axis labels (left side) */}
          <div style={{ position: "absolute", left: 0, top: 24, width: 100 }}>
            {symbols.map((sym, i) => (
              <div
                key={sym}
                className="flex items-center gap-1 text-[10px] font-mono truncate"
                style={{
                  height: cellSize + 1,
                  lineHeight: `${cellSize + 1}px`,
                  paddingRight: 4,
                  color: hoveredCell?.row === i ? "#fff" : stockSectors[sym]
                    ? (SECTOR_COLORS[stockSectors[sym]] || "#666")
                    : "#666",
                }}
              >
                <span
                  className="w-1.5 h-1.5 rounded-full inline-block flex-shrink-0"
                  style={{
                    background: SECTOR_COLORS[stockSectors[sym]] || "#666",
                  }}
                />
                <span className="truncate">{sym}</span>
              </div>
            ))}
          </div>

          {/* X-axis labels (top) */}
          <div
            style={{
              marginLeft: 104,
              height: 20,
              whiteSpace: "nowrap",
              position: "sticky",
              top: 0,
              zIndex: 10,
              background: "#111",
            }}
          >
            {symbols.map((sym, i) => (
              <span
                key={sym}
                className="text-[9px] font-mono inline-block truncate"
                style={{
                  width: cellSize + 1,
                  lineHeight: "20px",
                  textAlign: "center",
                  color: hoveredCell?.col === i ? "#fff" : "#666",
                  transform: "rotate(-45deg)",
                  transformOrigin: "left center",
                  marginTop: 14,
                }}
                title={sym}
              >
                {sym}
              </span>
            ))}
          </div>

          {/* Grid */}
          <div style={{ marginLeft: 104, marginTop: 50 }}>
            {matrix.map((row, i) => (
              <div key={i} style={{ display: "flex", height: cellSize + 1 }}>
                {row.map((val, j) => {
                  const isSelected =
                    selectedPair &&
                    ((selectedPair.sym1 === symbols[i] && selectedPair.sym2 === symbols[j]) ||
                      (selectedPair.sym1 === symbols[j] && selectedPair.sym2 === symbols[i]));
                  const isHoveredRow = hoveredCell?.row === i;
                  const isHoveredCol = hoveredCell?.col === j;
                  const isDiagonal = i === j;

                  return (
                    <div
                      key={j}
                      className={`
                        cursor-pointer transition-all duration-75
                        ${isDiagonal ? "cursor-default" : "hover:ring-1 hover:ring-white/40"}
                        ${isSelected ? "ring-2 ring-yellow-400 z-10" : ""}
                      `}
                      style={{
                        width: cellSize + 1,
                        height: cellSize + 1,
                        background: isDiagonal
                          ? "#1a1a1a"
                          : getCorrColor(val),
                        opacity: isHoveredRow || isHoveredCol ? 0.85 : 1,
                        position: "relative",
                        borderRadius: i === j ? "50%" : 1,
                      }}
                      onClick={() => handleCellClick(i, j)}
                      onMouseEnter={() =>
                        setHoveredCell({ row: i, col: j })
                      }
                      onMouseLeave={() => setHoveredCell(null)}
                      title={`${symbols[i]} / ${symbols[j]}: ${formatCorr(val)} (${getStrengthLabel(val)})`}
                    >
                      {/* Value tooltip on hover */}
                      {hoveredCell?.row === i && hoveredCell?.col === j && cellSize >= 14 && (
                        <div
                          className="absolute z-20 bg-zinc-900 border border-zinc-700 rounded px-1.5 py-0.5 text-[10px] font-mono whitespace-nowrap pointer-events-none shadow-lg"
                          style={{
                            top: -22,
                            left: "50%",
                            transform: "translateX(-50%)",
                          }}
                        >
                          <span className={val >= 0 ? "text-green-400" : "text-red-400"}>
                            {formatCorr(val)}
                          </span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Sector legend */}
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-zinc-500">
        {Object.entries(SECTOR_COLORS).map(([sector, color]) => {
          const count = symbols.filter((s) => stockSectors[s] === sector).length;
          if (count === 0) return null;
          return (
            <span key={sector} className="flex items-center gap-1">
              <span
                className="w-2 h-2 rounded-full inline-block flex-shrink-0"
                style={{ background: color }}
              />
              <span className="truncate max-w-[80px] sm:max-w-[120px]">
                {sector.replace(/_/g, " ")}
              </span>
              <span className="text-zinc-600">({count})</span>
            </span>
          );
        })}
      </div>
    </div>
  );
}
