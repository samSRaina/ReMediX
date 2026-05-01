import { useEffect, useState } from 'react';

export type SourceReference = {
  id: string;
  key: string;
  authors: string;
  title: string;
  journal: string | null;
  year: number | null;
  volume: string | null;
  issue: string | null;
  pages: string | null;
  doi: string | null;
  url: string | null;
  pmid: string | null;
  pmcid: string | null;
};

let cachedSources: SourceReference[] | null = null;
let inFlight: Promise<SourceReference[]> | null = null;

async function fetchSources(): Promise<SourceReference[]> {
  const response = await fetch('/data/sources/sources.json');
  if (!response.ok) {
    throw new Error(`Failed to load sources (${response.status})`);
  }
  return (await response.json()) as SourceReference[];
}

export async function getSources(): Promise<SourceReference[]> {
  if (cachedSources) return cachedSources;
  if (!inFlight) {
    inFlight = fetchSources();
  }
  cachedSources = await inFlight;
  return cachedSources;
}

export function useSources() {
  const [sources, setSources] = useState<SourceReference[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    getSources()
      .then((data) => {
        if (mounted) {
          setSources(data);
        }
      })
      .catch((err: unknown) => {
        if (mounted) {
          setSources([]);
          setError(err instanceof Error ? err.message : 'Failed to load sources');
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  return { sources, error };
}
