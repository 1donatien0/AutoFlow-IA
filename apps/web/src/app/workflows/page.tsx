"use client";

import { useCallback, useEffect, useState } from "react";
import { Card } from "@/components/Card";
import { ErrorBanner } from "@/components/Feedback";
import { api } from "@/lib/api";
import { useAction, useAuthGuard } from "@/lib/hooks";

interface Workflow {
  id: string;
  suggestion_id: string | null;
  name: string;
  status: string;
  kill_switch: boolean;
}

interface Execution {
  id: string;
  workflow_id: string;
  status: string;
  logs: { action?: string | null; status?: string; note?: string }[] | null;
  started_at: string | null;
}

interface SuggestionLite {
  id: string;
  title: string;
  status: string;
}

export default function WorkflowsPage() {
  const ready = useAuthGuard();
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [executions, setExecutions] = useState<Execution[]>([]);
  const [suggestions, setSuggestions] = useState<SuggestionLite[]>([]);
  const { busy, error, run } = useAction();

  const refresh = useCallback(async () => {
    const [w, e, s] = await Promise.all([
      api<Workflow[]>("/api/v1/workflows"),
      api<Execution[]>("/api/v1/workflows/executions"),
      api<SuggestionLite[]>("/api/v1/suggestions"),
    ]);
    setWorkflows(w);
    setExecutions(e);
    setSuggestions(s);
  }, []);

  useEffect(() => {
    if (ready) run(refresh);
  }, [ready, run, refresh]);

  const act = (fn: () => Promise<unknown>) =>
    run(async () => {
      await fn();
      await refresh();
    });

  const linked = new Set(workflows.map((w) => w.suggestion_id));
  const candidates = suggestions.filter((s) => s.status === "approved" && !linked.has(s.id));
  const names = Object.fromEntries(workflows.map((w) => [w.id, w.name]));

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Workflows — Phase 4</h1>
      <ErrorBanner message={error} />
      <Card title="Créer depuis une suggestion approuvée">
        <ul className="space-y-2">
          {candidates.map((s) => (
            <li key={s.id} className="flex justify-between items-center text-sm gap-3">
              <span>{s.title}</span>
              <button
                type="button"
                disabled={busy}
                onClick={() => act(() => api(`/api/v1/workflows/from-suggestion/${s.id}`, { method: "POST" }))}
                className="text-brand-600 underline"
              >
                Créer workflow
              </button>
            </li>
          ))}
          {candidates.length === 0 && (
            <li className="text-sm text-slate-500">Approuvez une suggestion pour pouvoir créer un workflow.</li>
          )}
        </ul>
      </Card>
      {workflows.map((w) => (
        <Card key={w.id} title={w.name}>
          <p className="text-sm text-slate-500 mb-3">
            Statut : {w.status}
            {w.kill_switch && <strong className="text-red-700"> — KILL SWITCH ACTIF</strong>}
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy || w.kill_switch}
              onClick={() =>
                act(() =>
                  api("/api/v1/workflows/execute", { method: "POST", body: JSON.stringify({ workflow_id: w.id }) }),
                )
              }
              className="px-4 py-2 bg-brand-600 text-white rounded disabled:opacity-50"
            >
              Exécuter (simulation)
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                act(() => api(`/api/v1/workflows/${w.id}/kill-switch?enabled=${!w.kill_switch}`, { method: "POST" }))
              }
              className={`px-4 py-2 rounded border ${
                w.kill_switch ? "border-green-600 text-green-700" : "border-red-600 text-red-700"
              }`}
            >
              {w.kill_switch ? "Réactiver" : "Arrêt d'urgence"}
            </button>
          </div>
        </Card>
      ))}
      <Card title="Exécutions récentes">
        {executions.map((e) => (
          <div key={e.id} className="border-b py-2 text-sm">
            <span className="font-medium">{e.status}</span> — {names[e.workflow_id] ?? e.workflow_id.slice(0, 8)}
            {e.started_at && (
              <span className="text-slate-400"> · {new Date(e.started_at).toLocaleString("fr-FR")}</span>
            )}
            {e.logs?.map((l, i) => (
              <p key={i} className="text-slate-500 pl-2">
                {l.action ?? "—"} : {l.note || l.status || "ok"}
              </p>
            ))}
          </div>
        ))}
        {executions.length === 0 && <p className="text-sm text-slate-500">Aucune exécution.</p>}
      </Card>
    </div>
  );
}
