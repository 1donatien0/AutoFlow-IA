"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { errorMessage, getToken } from "@/lib/api";

/** Redirige vers /login si aucun jeton n'est présent. Retourne true quand la page peut charger. */
export function useAuthGuard(): boolean {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  useEffect(() => {
    if (!getToken()) router.replace("/login");
    else setReady(true);
  }, [router]);
  return ready;
}

/** Exécute une action asynchrone en exposant l'état de chargement et l'erreur éventuelle. */
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const run = useCallback(async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
    setBusy(true);
    setError("");
    try {
      return await fn();
    } catch (err) {
      setError(errorMessage(err));
      return undefined;
    } finally {
      setBusy(false);
    }
  }, []);
  return { busy, error, setError, run };
}
