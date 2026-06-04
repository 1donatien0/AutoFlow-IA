"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/Card";
import { ErrorBanner, Loading } from "@/components/Feedback";
import { api, errorMessage } from "@/lib/api";
import { useAuthGuard } from "@/lib/hooks";

interface Metrics {
  hours_lost_estimate: number;
  repetitive_tasks_count: number;
  automation_potential_score: number;
  category_breakdown: Record<string, number>;
  insights: { label: string; value: string; detail?: string | null }[];
}

interface EventRow {
  id: string;
  subject: string | null;
  category: string;
  confidence: number;
}

export default function DashboardPage() {
  const ready = useAuthGuard();
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [events, setEvents] = useState<EventRow[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!ready) return;
    Promise.all([
      api<Metrics>("/api/v1/observation/dashboard"),
      api<EventRow[]>("/api/v1/observation/events?limit=10"),
    ])
      .then(([m, e]) => {
        setMetrics(m);
        setEvents(e);
      })
      .catch((err) => setError(errorMessage(err)));
  }, [ready]);

  if (error) return <ErrorBanner message={error} />;
  if (!metrics) return <Loading />;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">Dashboard — Observation</h1>
        <p className="text-slate-600 text-sm mt-1">Phase 1 : métriques sans automatisation externe</p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white p-6 rounded-xl border">
          <p className="text-sm text-slate-500">Temps passé estimé</p>
          <p className="text-3xl font-bold text-red-600">{metrics.hours_lost_estimate} h</p>
          <p className="text-xs text-slate-400">sur 30 jours</p>
        </div>
        <div className="bg-white p-6 rounded-xl border">
          <p className="text-sm text-slate-500">Catégories répétitives</p>
          <p className="text-3xl font-bold">{metrics.repetitive_tasks_count}</p>
          <p className="text-xs text-slate-400">≥ 5 emails / 30 jours</p>
        </div>
        <div className="bg-white p-6 rounded-xl border">
          <p className="text-sm text-slate-500">Potentiel d&apos;automatisation</p>
          <p className="text-3xl font-bold text-brand-600">{metrics.automation_potential_score} / 100</p>
        </div>
      </div>

      <Card title="Insights">
        <ul className="space-y-3">
          {metrics.insights.map((i) => (
            <li key={i.label} className="border-l-4 border-brand-500 pl-4">
              <span className="font-medium">{i.label}</span> — {i.value}
              {i.detail && <p className="text-sm text-slate-500">{i.detail}</p>}
            </li>
          ))}
        </ul>
      </Card>

      <Card title="Répartition par catégorie">
        <div className="flex flex-wrap gap-3">
          {Object.entries(metrics.category_breakdown).map(([cat, n]) => (
            <span key={cat} className="px-3 py-1 bg-slate-100 rounded-full text-sm">
              {cat} : {n}
            </span>
          ))}
          {Object.keys(metrics.category_breakdown).length === 0 && (
            <p className="text-slate-500 text-sm">Synchronisez des emails depuis Intégrations</p>
          )}
        </div>
      </Card>

      <Card title="Derniers emails classifiés">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500 border-b">
                <th className="py-2">Sujet</th>
                <th>Catégorie</th>
                <th>Confiance</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.id} className="border-b border-slate-100">
                  <td className="py-2 pr-4">{e.subject || "(sans objet)"}</td>
                  <td className="pr-4">{e.category}</td>
                  <td>{(e.confidence * 100).toFixed(0)} %</td>
                </tr>
              ))}
            </tbody>
          </table>
          {events.length === 0 && <p className="text-slate-500 text-sm mt-2">Aucun email pour le moment.</p>}
        </div>
      </Card>
    </div>
  );
}
