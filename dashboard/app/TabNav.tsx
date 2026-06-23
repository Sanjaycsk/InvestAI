import Link from "next/link";

// Top-level tabs: the main dashboard and the coffee-shop panel.
export default function TabNav({ active }: { active: "home" | "coffee" }) {
  return (
    <nav className="tabnav">
      <Link href="/" className={active === "home" ? "active" : ""}>
        📊 Today
      </Link>
      <Link href="/coffee" className={active === "coffee" ? "active" : ""}>
        ☕ Coffee Shop
      </Link>
    </nav>
  );
}
