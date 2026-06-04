"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Card } from "@/components/Card";
import { ErrorBanner, SuccessBanner } from "@/components/Feedback";
import { api } from "@/lib/api";
import { useAction, useAuthGuard } from "@/lib/hooks";

type Provider = "gmail" | "outlook";

interface Integration {
  id: string;
  provider: string;
  status: string;
  last_sync_at: string | null;
}

const LABELS: Record<string, string> = { gmail: "Gmail", outlook: "Outlook" };

function IntegrationsContent() {
  const ready = useAuthGuard();
  const params = useSearchParams();
  const [message, setMessage] = useState("");
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const { busy, error, setError, run } = useAction();

  const load = useCallback(async () => {
    setIntegrations(await api<Integration[]>("/api/v1/integrations"));
  }, []);

  useEffect(() => {
    if (!ready) return;
    const connected = params.get("connected");
    const failed = params.get("error");
    if (connected) setMessage(`${LABELS[connected] ?? "Intégration"} connecté avec succès`);
    if (failed) setError(`La connexion ${LABELS[failed] ?? ""} a échoué ou a été annulée.`);
    run(load);
  }, [ready, params, load, run, setError]);

  async function connect(provider: Provider) {
    const data = await run(() => api<{ auth_url: string }>(`/api/v1/integrations/${provider}/connect`));
    if (data) window.location.href = data.auth_url;
  }

  async function sync(provider: Provider | "demo") {
    setMessage("");
    const r = await run(() =>
      api<{ ingested: number }>("/api/v1/integrations/sync", {
        method: "POST",
        body: JSON.stringify({ provider, demo: provider === "demo" }),
      }),
    );
    if (r) {
      setMessage(
        provider === "demo"
          ? `${r.ingested} emails démo ingérés et classifiés`
          : `${r.ingested} nouveaux emails ${LABELS[provider]} synchronisés`,
      );
      await run(load);
    }
  }

  const byProvider = Object.fromEntries(integrations.map((i) => [i.provider, i]));

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Intégrations</h1>
      <SuccessBanner message={message} />
      <ErrorBanner message={error} />
      <Card title="Email (lecture seule)">
        <p className="text-sm text-slate-600 mb-4">
          OAuth Gmail / Outlook — scopes de lecture uniquement (Phases 1–3). Les jetons sont chiffrés au repos.
        </p>
        <div className="space-y-3">
          {(["gmail", "outlook"] as Provider[]).map((p) => {
            const integ = byProvider[p];
            const connected = integ?.status === "connected";
            return (
              <div key={p} className="flex flex-wrap items-center gap-3 border rounded-lg p-3">
                <span className="font-medium w-24">{LABELS[p]}</span>
                <span className={`text-xs px-2 py-1 rounded ${connected ? "bg-green-100 text-green-800" : "bg-slate-100"}`}>
                  {integ?.status ?? "non connecté"}
                </span>
                {integ?.last_sync_at && (
                  <span className="text-xs text-slate-500">
                    Dernière synchro : {new Date(integ.last_sync_at).toLocaleString("fr-FR")}
                  </span>
                )}
                <div className="flex gap-2 ml-auto">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => connect(p)}
                    className="px-3 py-1.5 border border-brand-600 text-brand-600 rounded text-sm disabled:opacity-60"
                  >
                    {connected ? "Reconnecter" : "Connecter"}
                  </button>
                  {connected && (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => sync(p)}
                      className="px-3 py-1.5 bg-brand-600 text-white rounded text-sm disabled:opacity-60"
                    >
                      Synchroniser
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
        <button
          type="button"
          disabled={busy}
          onClick={() => sync("demo")}
          className="mt-4 px-4 py-2 bg-slate-200 rounded disabled:opacity-60"
        >
          Charger données démo (cabinet comptable)
        </button>
      </Card>
      <Card title="À venir — Phase 4+">
        <ul className="text-sm text-slate-600 list-disc pl-5 space-y-1">
          <li>Microsoft 365, Google Workspace</li>
          <li>Excel, HubSpot, Salesforce, Slack, Notion</li>
        </ul>
      </Card>
    </div>
  );
}

export default function IntegrationsPage() {
  return (
    <Suspense fallback={<p className="text-slate-500">Chargement…</p>}>
      <IntegrationsContent />
    </Suspense>
  );
}
