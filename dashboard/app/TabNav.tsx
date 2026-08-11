import Link from "next/link";
import { Dashboard, Search } from "./Icons";

// Top-level tabs: today's quick-skim view, and "Details" — the stock
// look-up tool plus everything that isn't a today-only decision (error
// patterns, yesterday's whole-portfolio recap, how the model works). Keeps
// the home page a fast skim; this tab is where you go to dig in.
export default function TabNav({ active }: { active: "home" | "lookup" }) {
  return (
    <nav className="tabnav">
      <Link href="/" className={active === "home" ? "active" : ""}>
        <Dashboard size={16} /> Today
      </Link>
      <Link href="/lookup" className={active === "lookup" ? "active" : ""}>
        <Search size={16} /> Details
      </Link>
    </nav>
  );
}
