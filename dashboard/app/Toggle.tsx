"use client";

// iOS-style switch used to flip a card between compact and detailed views.
// Accessible: real <button role="switch"> with aria-checked.
export default function Toggle({
  on,
  onChange,
  label,
}: {
  on: boolean;
  onChange: (v: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      className="switch"
      onClick={() => onChange(!on)}
    >
      <span className="switch-text">{label}</span>
      <span className={`switch-track${on ? " on" : ""}`} aria-hidden="true">
        <span className="switch-thumb" />
      </span>
    </button>
  );
}
