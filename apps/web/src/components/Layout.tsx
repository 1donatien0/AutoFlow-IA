"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearToken } from "@/lib/api";

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/integrations", label: "Intégrations" },
  { href: "/processes", label: "Processus" },
  { href: "/suggestions", label: "Suggestions" },
  { href: "/workflows", label: "Workflows" },
  { href: "/agents", label: "Agents" },
  { href: "/predictions", label: "Prédictions" },
  { href: "/settings", label: "Données & RGPD" },
];

export function Layout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  if (pathname === "/login") return <>{children}</>;

  return (
    <div className="min-h-screen flex flex-col md:flex-row">
      <aside className="md:w-56 bg-brand-900 text-white p-4 flex flex-col">
        <div className="mb-6 md:mb-8">
          <p className="text-lg font-bold">AutoFlow AI</p>
          <p className="text-xs text-slate-300 mt-1">Observer → Automatiser</p>
        </div>
        <nav className="flex-1 flex md:block gap-1 overflow-x-auto md:space-y-1" aria-label="Navigation principale">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={pathname === item.href ? "page" : undefined}
              className={`block whitespace-nowrap px-3 py-2 rounded text-sm ${
                pathname === item.href ? "bg-brand-600" : "hover:bg-white/10"
              }`}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <button
          type="button"
          onClick={() => {
            clearToken();
            router.push("/login");
          }}
          className="text-sm text-slate-300 hover:text-white mt-4 text-left"
        >
          Déconnexion
        </button>
      </aside>
      <main className="flex-1 p-4 md:p-8 overflow-auto">{children}</main>
    </div>
  );
}
