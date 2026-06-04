"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/Card";
import { ErrorBanner } from "@/components/Feedback";
import { api } from "@/lib/api";
import { useAction, useAuthGuard } from "@/lib/hooks";

interface Process {
  id: string;
  name: string;
  trigger_label: string;
  steps: string[];
  frequency: number;
  avg_duration_minutes: number;
}

export default function ProcessesPage() {
  const ready = useAuthGuard();
  const [processes, setProcesses] = useState<Process[]>([]);
  const { busy, error, run } = useAction();

  useEffect(() => {
    if (ready) run(async () => setProcesses(await api<Process[]>("/api/v1/processes")));
  }, [ready, run]);

  async function discover() {
    const list = await run(() => api<Process[]>("/api/v1/processes/discover", { method: "POST" }));
    if (list) setProcesses(list);
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap gap-3 justify-between items-center">
        <h1 className="text-2xl font-bold">Processus découverts</h1>
        <button
          type="button"
          onClick={discover}
          disabled={busy}
          className="px-4 py-2 bg-brand-600 text-white rounded disabled:opacity-60"
        >
          {busy ? "Analyse…" : "Lancer découverte"}
        </button>
      </header>
      <p className="text-sm text-slate-600">
        Phase 2 — Process mining : séquences d&apos;emails récurrentes par fil de discussion, détectées sans saisie.
      </p>
      <ErrorBanner message={error} />
      {processes.map((p) => (
        <Card key={p.id} title={p.name}>
          <p className="text-sm text-slate-500 mb-2">
            Déclencheur : {p.trigger_label} — {p.frequency}× — ~{p.avg_duration_minutes} min de bout en bout
          </p>
          <div className="flex items-center gap-2 flex-wrap">
            {p.steps.map((s, i) => (
              <span key={`${s}-${i}`} className="flex items-center gap-2">
                <span className="px-2 py-1 bg-brand-50 text-brand-900 rounded text-sm">{s}</span>
                {i < p.steps.length - 1 && <span aria-hidden>→</span>}
              </span>
            ))}
          </div>
        </Card>
      ))}
      {processes.length === 0 && !busy && (
        <p className="text-slate-500">Ingérez des emails puis cliquez sur « Lancer découverte ».</p>
      )}
    </div>
  );
}
