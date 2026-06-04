"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/Card";
import { ErrorBanner } from "@/components/Feedback";
import { api } from "@/lib/api";
import { useAction, useAuthGuard } from "@/lib/hooks";

interface Prediction {
  id: string;
  prediction_type: string;
  entity_ref: string;
  score: number;
  explanation: string;
}

const LABELS: Record<string, string> = {
  payment_delay_risk: "Risque retard paiement",
  validation_steps: "Échanges avant validation (devis)",
  commercial_closing: "Indicateur d'activité commerciale",
};

export default function PredictionsPage() {
  const ready = useAuthGuard();
  const [items, setItems] = useState<Prediction[]>([]);
  const { busy, error, run } = useAction();

  useEffect(() => {
    if (ready) run(async () => setItems(await api<Prediction[]>("/api/v1/predictions")));
  }, [ready, run]);

  async function generate() {
    const list = await run(() => api<Prediction[]>("/api/v1/predictions/generate", { method: "POST" }));
    if (list) setItems(list);
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap gap-3 justify-between">
        <h1 className="text-2xl font-bold">Intelligence prédictive</h1>
        <button
          type="button"
          onClick={generate}
          disabled={busy}
          className="px-4 py-2 bg-brand-600 text-white rounded disabled:opacity-60"
        >
          Générer prédictions
        </button>
      </header>
      <p className="text-sm text-slate-600">
        Scores heuristiques calculés sur les emails des 90 derniers jours — à utiliser comme aide à la décision.
      </p>
      <ErrorBanner message={error} />
      {items.map((p) => (
        <Card key={p.id} title={LABELS[p.prediction_type] || p.prediction_type}>
          <p className="text-2xl font-bold text-brand-600">{(p.score * 100).toFixed(0)} %</p>
          <p className="text-sm text-slate-500 mt-1">{p.entity_ref}</p>
          <p className="mt-3">{p.explanation}</p>
        </Card>
      ))}
      {items.length === 0 && !busy && (
        <p className="text-slate-500">Ingérez des données puis générez les prédictions.</p>
      )}
    </div>
  );
}
