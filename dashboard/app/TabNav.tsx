import Link from "next/link";
import { Dashboard, Coffee } from "./Icons";

// Top-level tabs: the main dashboard and the coffee-shop panel.
export default function TabNav({ active }: { active: "home" | "coffee" }) {
  return (
    <nav className="tabnav">
      <Link href="/" className={active === "home" ? "active" : ""}>
        <Dashboard size={16} /> Today
      </Link>
      <Link href="/coffee" className={active === "coffee" ? "active" : ""}>
        <Coffee size={16} /> Coffee Shop
      </Link>
    </nav>
  );
}
