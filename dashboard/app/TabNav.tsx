import Link from "next/link";
import { Dashboard, Search } from "./Icons";

// Top-level tabs: today's quick-skim view, and a deep-dive lookup for any
// one stock (yesterday's call, its own track record, coffee-shop opinions).
// The old "Coffee Shop" tab was folded into the lookup detail per-stock
// instead of being its own separate page.
export default function TabNav({ active }: { active: "home" | "lookup" }) {
  return (
    <nav className="tabnav">
      <Link href="/" className={active === "home" ? "active" : ""}>
        <Dashboard size={16} /> Today
      </Link>
      <Link href="/lookup" className={active === "lookup" ? "active" : ""}>
        <Search size={16} /> Look up a stock
      </Link>
    </nav>
  );
}
