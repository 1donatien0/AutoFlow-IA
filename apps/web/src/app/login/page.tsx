"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ErrorBanner } from "@/components/Feedback";
import { api, setToken } from "@/lib/api";
import { useAction } from "@/lib/hooks";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [orgName, setOrgName] = useState("");
  const { busy, error, run } = useAction();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const data = await run(() =>
      api<{ access_token: string }>(mode === "login" ? "/api/v1/auth/login" : "/api/v1/auth/register", {
        method: "POST",
        body: JSON.stringify(
          mode === "login"
            ? { email, password }
            : { email, password, organization_name: orgName, full_name: fullName },
        ),
      }),
    );
    if (data) {
      setToken(data.access_token);
      router.push("/dashboard");
    }
  }

  const input = "w-full border rounded px-3 py-2";

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-brand-900 to-slate-800 p-4">
      <form onSubmit={submit} className="bg-white p-8 rounded-xl shadow-xl w-full max-w-md space-y-4">
        <h1 className="text-2xl font-bold text-brand-900">AutoFlow AI</h1>
        <p className="text-sm text-slate-600">Plateforme d&apos;observation — cabinets comptables</p>
        {mode === "register" && (
          <>
            <label className="block text-sm">
              <span className="sr-only">Nom du cabinet</span>
              <input
                className={input}
                placeholder="Nom du cabinet"
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                minLength={2}
                maxLength={255}
                required
              />
            </label>
            <label className="block text-sm">
              <span className="sr-only">Nom complet</span>
              <input
                className={input}
                placeholder="Votre nom (optionnel)"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                maxLength={255}
                autoComplete="name"
              />
            </label>
          </>
        )}
        <label className="block text-sm">
          <span className="sr-only">Email</span>
          <input
            className={input}
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            required
          />
        </label>
        <label className="block text-sm">
          <span className="sr-only">Mot de passe</span>
          <input
            className={input}
            type="password"
            placeholder="Mot de passe (8 caractères minimum)"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={mode === "register" ? 8 : 1}
            maxLength={72}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            required
          />
        </label>
        <ErrorBanner message={error} />
        <button
          type="submit"
          disabled={busy}
          className="w-full bg-brand-600 text-white py-2 rounded font-medium hover:bg-brand-500 disabled:opacity-60"
        >
          {busy ? "…" : mode === "login" ? "Connexion" : "Créer un compte"}
        </button>
        <button
          type="button"
          className="text-sm text-brand-600 w-full"
          onClick={() => setMode(mode === "login" ? "register" : "login")}
        >
          {mode === "login" ? "Créer un compte" : "Déjà inscrit ?"}
        </button>
      </form>
    </div>
  );
}
