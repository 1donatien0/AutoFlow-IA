"use client";

import { useState } from "react";
import { Card } from "@/components/Card";
import { ErrorBanner } from "@/components/Feedback";
import { api } from "@/lib/api";
import { useAction, useAuthGuard } from "@/lib/hooks";

const AGENTS = [
  { id: "commercial", label: "Commercial", desc: "Devis, suivi prospect, relances" },
  { id: "facturation", label: "Facturation", desc: "Factures, rappels, paiements" },
  { id: "support", label: "Support", desc: "FAQ, tickets, réponses email" },
  { id: "operations", label: "Opérations", desc: "Planification, dossiers, tâches" },
];

export default function AgentsPage() {
  const ready = useAuthGuard();
  const [task, setTask] = useState("Analyser les relances factures du mois");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const { busy, error, run } = useAction();

  async function runAgent(agentType: string) {
    const r = await run(() =>
      api<{ result: Record<string, unknown> }>("/api/v1/agents/run", {
        method: "POST",
        body: JSON.stringify({ agent_type: agentType, task }),
      }),
    );
    if (r) setResult(r.result);
  }

  if (!ready) return null;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Agents IA spécialisés</h1>
      <label className="block">
        <span className="text-sm text-slate-600">Tâche à confier à l&apos;agent</span>
        <textarea
          className="mt-1 w-full border rounded p-3 text-sm"
          rows={3}
          maxLength={4000}
          value={task}
          onChange={(e) => setTask(e.target.value)}
        />
      </label>
      <ErrorBanner message={error} />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {AGENTS.map((a) => (
          <Card key={a.id} title={a.label}>
            <p className="text-sm text-slate-600 mb-3">{a.desc}</p>
            <button
              type="button"
              disabled={busy || !task.trim()}
              onClick={() => runAgent(a.id)}
              className="px-3 py-1 bg-brand-600 text-white rounded text-sm disabled:opacity-60"
            >
              Exécuter
            </button>
          </Card>
        ))}
      </div>
      {result && (
        <Card title="Résultat">
          <pre className="text-xs bg-slate-100 p-4 rounded overflow-auto">{JSON.stringify(result, null, 2)}</pre>
        </Card>
      )}
    </div>
  );
}
