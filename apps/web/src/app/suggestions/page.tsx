"use client";

import { useCallback, useEffect, useState } from "react";
import { Card } from "@/components/Card";
import { ErrorBanner } from "@/components/Feedback";
import { api } from "@/lib/api";
import { useAction, useAuthGuard } from "@/lib/hooks";

interface Suggestion {
  id: string;
  title: string;
  description: string;
  monthly_frequency: number;
  estimated_hours_saved: number;
  workflow_draft: { readable?: string } | null;
  status: "draft" | "approved" | "rejected";
  roi_score: number;
  risk_notes: string | null;
}

const STATUS_LABEL: Record<Suggestion["status"], string> = {
  draft: "Brouillon",
  approved: "Approuvée",
  rejected: "Rejetée",
};

export default function SuggestionsPage() {
  const ready = useAuthGuard();
  const [items, setItems] = useState<Suggestion[]>([]);
  const { busy, error, run } = useAction();

  const load = useCallback(async () => setItems(await api<Suggestion[]>("/api/v1/suggestions")), []);

  useEffect(() => {
    if (ready) run(load);
  }, [ready, run, load]);

  async function generate() {
    const list = await run(() => api<Suggestion[]>("/api/v1/suggestions/generate", { method: "POST" }));
    if (list) setItems(list);
  }

  async function setStatus(id: string, status: Suggestion["status"]) {
    await run(async () => {
      await api(`/api/v1/suggestions/${id}`, { method: "PATCH", body: JSON.stringify({ status }) });
      await load();
    });
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap gap-3 justify-between">
        <h1 className="text-2xl font-bold">Suggestions IA</h1>
        <button
          type="button"
          onClick={generate}
          disabled={busy}
          className="px-4 py-2 bg-brand-600 text-white rounded disabled:opacity-60"
        >
          Générer suggestions
        </button>
      </header>
      <ErrorBanner message={error} />
      {items.map((s) => (
        <Card
          key={s.id}
          title={s.title}
          action={
            s.status === "draft" ? (
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => setStatus(s.id, "approved")}
                  className="text-sm px-3 py-1 bg-green-600 text-white rounded"
                >
                  Approuver
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => setStatus(s.id, "rejected")}
                  className="text-sm px-3 py-1 border rounded"
                >
                  Rejeter
                </button>
              </div>
            ) : (
              <span className={`text-sm ${s.status === "approved" ? "text-green-700" : "text-slate-500"}`}>
                {STATUS_LABEL[s.status]}
              </span>
            )
          }
        >
          <p>{s.description}</p>
          <p className="text-sm mt-2 text-slate-500">
            Score ROI {s.roi_score}/100 — Gain estimé {s.estimated_hours_saved} h/mois
          </p>
          {s.workflow_draft?.readable && (
            <pre className="mt-3 p-3 bg-slate-100 rounded text-xs whitespace-pre-wrap">{s.workflow_draft.readable}</pre>
          )}
          {s.risk_notes && <p className="text-xs text-amber-700 mt-2">{s.risk_notes}</p>}
        </Card>
      ))}
      {items.length === 0 && !busy && (
        <p className="text-slate-500">
          Aucune suggestion. Ingérez des emails puis cliquez sur « Générer suggestions ».
        </p>
      )}
    </div>
  );
}
