export function ErrorBanner({ message }: { message: string }) {
  if (!message) return null;
  return (
    <p role="alert" className="bg-red-50 text-red-800 border border-red-200 px-4 py-2 rounded text-sm">
      {message}
    </p>
  );
}

export function SuccessBanner({ message }: { message: string }) {
  if (!message) return null;
  return (
    <p role="status" className="bg-green-50 text-green-800 border border-green-200 px-4 py-2 rounded text-sm">
      {message}
    </p>
  );
}

export function Loading() {
  return <p className="text-slate-500">Chargement…</p>;
}
