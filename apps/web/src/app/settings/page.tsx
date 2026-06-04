"use client";

import { useCallback, useEffect, useState } from "react";
import { Card } from "@/components/Card";
import { ErrorBanner, SuccessBanner } from "@/components/Feedback";
import { api } from "@/lib/api";
import { useAction, useAuthGuard } from "@/lib/hooks";

interface AuditLog {
  id: string;
  action: string;
  actor: string | null;
  created_at: string;
}

export default function SettingsPage() {
  const ready = useAuthGuard();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [message, setMessage] = useState("");
  const [confirmText, setConfirmText] = useState("");
  const { busy, error, run } = useAction();

  const load = useCallback(async () => setLogs(await api<AuditLog[]>("/api/v1/organization/audit-logs?limit=50")), []);

  useEffect(() => {
    if (ready) run(load);
  }, [ready, run, load]);

  async function exportData() {
    const data = await run(() => api<Record<string, unknown>>("/api/v1/organization/export"));
    if (!data) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `autoflow-export-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
    setMessage("Export téléchargé.");
    await run(load);
  }

  async function purge() {
    const r = await run(() =>
      api<{ deleted: Record<string, number> }>("/api/v1/organization/data?confirm=true", { method: "DELETE" }),
    );
    if (r) {
      const total = Object.values(r.deleted).reduce((a, b) => a + b, 0);
      setMessage(`${total} enregistrements supprimés.`);
      setConfirmText("");
      await run(load);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Données & RGPD</h1>
      <SuccessBanner message={message} />
      <ErrorBanner message={error} />
      <Card title="Export des données (droit d'accès / portabilité)">
        <p className="text-sm text-slate-600 mb-3">
          Télécharge toutes les données de votre organisation au format JSON (hors mots de passe et jetons OAuth).
        </p>
        <button type="button" disabled={busy} onClick={exportData} className="px-4 py-2 bg-brand-600 text-white rounded">
          Exporter
        </button>
      </Card>
      <Card title="Effacement des données (droit à l'effacement)">
        <p className="text-sm text-slate-600 mb-3">
          Supprime définitivement emails observés, processus, suggestions, workflows, prédictions et intégrations.
          Votre compte et le journal d&apos;audit sont conservés. Tapez <strong>SUPPRIMER</strong> pour confirmer.
        </p>
        <div className="flex flex-wrap gap-2">
          <input
            className="border rounded px-3 py-2 text-sm"
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
            placeholder="SUPPRIMER"
            aria-label="Confirmation de suppression"
          />
          <button
            type="button"
            disabled={busy || confirmText !== "SUPPRIMER"}
            onClick={purge}
            className="px-4 py-2 bg-red-600 text-white rounded disabled:opacity-50"
          >
            Tout effacer
          </button>
        </div>
      </Card>
      <Card title="Journal d'audit">
        <ul className="text-sm divide-y">
          {logs.map((l) => (
            <li key={l.id} className="py-2 flex flex-wrap gap-x-3">
              <span className="text-slate-400">{new Date(l.created_at).toLocaleString("fr-FR")}</span>
              <span className="font-medium">{l.action}</span>
              {l.actor && <span className="text-slate-500">{l.actor}</span>}
            </li>
          ))}
          {logs.length === 0 && <li className="py-2 text-slate-500">Aucune entrée.</li>}
        </ul>
      </Card>
    </div>
  );
}
