import mlTrend from "@/data/ml_trend.json";

// A traditional ML model (gradient boosting on price/technical features),
// SEPARATE from the daily LLM agent — a second opinion on where each name
// might be headed over the next 15 trading days. Built by
// `backtest/train_ml_trend.py` (runs locally; yfinance needs a home IP),
// written to this static JSON, same storage-tier pattern as `backtest.json`.
//
// Honesty first: `validation` is a walk-forward backtest, and as of the
// first training run it does NOT beat the naive "always guess Flat"
// baseline — surfaced prominently below rather than hidden, matching the
// rest of this dashboard's calibration-reality-check ethos.

export type MLClass = "Up" | "Down" | "Flat";

export type MLPrediction = {
  ticker: string;
  sector: string;
  as_of_date: string;
  predicted_class: MLClass;
  confidence_pct: number;
  class_probs: Record<MLClass, number>;
};

type MLValidation = {
  error?: string;
  accuracy_pct?: number;
  baseline_class?: string;
  baseline_accuracy_pct?: number;
  beats_baseline?: boolean;
};

type MLTrendData = {
  horizon_trading_days: number;
  validation: MLValidation;
  live_track_record: { n_graded: number; accuracy_pct: number } | null;
  predictions: MLPrediction[];
};

const data = mlTrend as unknown as MLTrendData;

export function mlPredictionFor(ticker: string | null): MLPrediction | null {
  if (!ticker) return null;
  return data.predictions.find((p) => p.ticker === ticker) ?? null;
}

// Read from the data file rather than hardcoded, so a future horizon change
// (this has already moved 15 -> 5 once) doesn't leave stale UI copy behind.
export const ML_HORIZON_DAYS = data.horizon_trading_days;

export const CLASS_META: Record<MLClass, { arrow: string; text: string; cls: string }> = {
  Up: { arrow: "▲", text: "Up", cls: "pos" },
  Down: { arrow: "▼", text: "Down", cls: "neg" },
  Flat: { arrow: "▬", text: "Flat", cls: "" },
};

export default function MLTrendPanel() {
  const v = data.validation;
  const preds = [...data.predictions].sort((a, b) => b.confidence_pct - a.confidence_pct);

  return (
    <div className="mltrend">
      <div className={`mltrend-reality ${v.beats_baseline ? "pos" : "neg"}`}>
        <strong>Reality check:</strong>{" "}
        {v.error || v.accuracy_pct === undefined ? (
          "Not enough price history yet to validate this model honestly."
        ) : v.beats_baseline ? (
          <>
            Over its walk-forward backtest, this model&apos;s {data.horizon_trading_days}-day
            call has been right <strong>{v.accuracy_pct}%</strong> of the time — better than
            just guessing &quot;{v.baseline_class}&quot; every time ({v.baseline_accuracy_pct}%).
          </>
        ) : (
          <>
            Over its walk-forward backtest, this model&apos;s {data.horizon_trading_days}-day
            call has been right <strong>{v.accuracy_pct}%</strong> of the time — actually{" "}
            <strong>worse</strong> than just guessing &quot;{v.baseline_class}&quot;
            every time ({v.baseline_accuracy_pct}%). Treat these as early-stage and
            experimental, not something to act on yet.
          </>
        )}
      </div>

      <p className="explain top">
        {data.live_track_record ? (
          <>
            Live track record (its own actual graded calls, not the backtest):{" "}
            <strong>{data.live_track_record.accuracy_pct}%</strong> right over{" "}
            {data.live_track_record.n_graded} calls so far.
          </>
        ) : (
          <>
            No live graded calls yet — each prediction needs{" "}
            {data.horizon_trading_days} trading days to resolve, so check back in a
            few weeks for a real (not backtested) track record.
          </>
        )}
      </p>

      <ul className="stock-list">
        {preds.map((p, i) => {
          const meta = CLASS_META[p.predicted_class];
          return (
            <li className="stock-row" key={i}>
              <div className="stock-main">
                <span className="ticker">{p.ticker}</span>
              </div>
              <div className="stock-meta">
                <span className={`dir ${meta.cls}`}>
                  {meta.arrow} {meta.text}
                </span>
                <span className="conf">{p.confidence_pct}% sure</span>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
