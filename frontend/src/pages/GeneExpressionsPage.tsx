import { Loader2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { AppLayout, Surface } from '../components/Layout';
import { getGeneExpressions } from '../lib/api';
import type { GeneExpressionsResponse } from '../types/api';

export function GeneExpressionsPage() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [payload, setPayload] = useState<GeneExpressionsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await getGeneExpressions(page, pageSize, search || undefined);
        setPayload(data);
      } catch (err) {
        setPayload(null);
        setError(err instanceof Error ? err.message : 'Failed to load gene expressions');
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, [page, pageSize, search]);

  return (
    <AppLayout title="Gene Expressions" subtitle="Search and explore expression signatures">
      <Surface>
        <div className="grid gap-4 md:grid-cols-[2fr_1fr_1fr] md:items-end">
          <label className="space-y-2">
            <span className="text-sm font-medium">Search by Gene Symbol</span>
            <input
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault();
                  setPage(1);
                  setSearch(searchInput.trim());
                }
              }}
              className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none ring-cyan-400 transition focus:border-cyan-400 focus:ring"
              placeholder="TRPC6, CSF3R..."
            />
          </label>

          <button
            type="button"
            className="rounded-xl bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm shadow-cyan-600/30 transition hover:-translate-y-0.5 hover:bg-cyan-500"
            onClick={() => {
              setPage(1);
              setSearch(searchInput.trim());
            }}
          >
            Search
          </button>

          <button
            type="button"
            className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:-translate-y-0.5 hover:border-cyan-300 hover:bg-cyan-50"
            onClick={() => {
              setSearchInput('');
              setSearch('');
              setPage(1);
            }}
          >
            Clear
          </button>
        </div>

        <div className="mt-4 flex items-center justify-between text-sm text-slate-600">
          <span>
            {payload
              ? `Showing ${(payload.page - 1) * payload.page_size + 1}–${Math.min(payload.page * payload.page_size, payload.total)} of ${payload.total.toLocaleString()}`
              : 'No results'}
          </span>
          <label className="inline-flex items-center gap-2">
            Rows per page
            <select
              value={pageSize}
              onChange={(event) => {
                setPageSize(Number(event.target.value));
                setPage(1);
              }}
                className="rounded-lg border border-slate-300 bg-white px-2 py-1"
            >
              {[25, 50, 100].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
        </div>

        <div className="table-shell mt-4">
          {loading ? (
            <div className="flex items-center gap-2 p-6 text-sm text-slate-600"><Loader2 className="animate-spin" size={16} />Loading...</div>
          ) : error ? (
            <div className="p-4 text-sm text-red-700">{error}</div>
          ) : !payload || payload.data.length === 0 ? (
            <div className="p-6 text-sm text-slate-500">No gene expression data found.</div>
          ) : (
            <table className="table-ui">
              <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                <tr><th className="px-3 py-2">ID</th><th className="px-3 py-2">adj.P.Val</th><th className="px-3 py-2">logFC</th><th className="px-3 py-2">Gene Symbol</th></tr>
              </thead>
              <tbody>
                {payload.data.map((row: Record<string, string | number | null>, idx: number) => (
                  <tr key={`${row['Gene.symbol'] || 'g'}-${idx}`}>
                    <td className="px-3 py-2">{String(row['ID'] ?? '-')}</td>
                    <td className="px-3 py-2">{row['adj.P.Val'] == null ? '-' : Number(row['adj.P.Val']).toExponential(2)}</td>
                    <td className={`px-3 py-2 ${Number(row['logFC']) > 0 ? 'text-emerald-700' : Number(row['logFC']) < 0 ? 'text-rose-700' : ''}`}>
                      {row['logFC'] == null ? '-' : Number(row['logFC']).toFixed(6)}
                    </td>
                    <td className="px-3 py-2 font-medium">{String(row['Gene.symbol'] ?? '-')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {payload && payload.total_pages > 1 ? (
          <div className="mt-4 flex items-center justify-center gap-2">
            <button className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm transition hover:border-cyan-300 hover:bg-cyan-50 disabled:opacity-50" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>Prev</button>
            <span className="text-sm text-slate-600">Page {payload.page} / {payload.total_pages}</span>
            <button className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm transition hover:border-cyan-300 hover:bg-cyan-50 disabled:opacity-50" disabled={page >= payload.total_pages} onClick={() => setPage((p) => Math.min(payload.total_pages, p + 1))}>Next</button>
          </div>
        ) : null}
      </Surface>
    </AppLayout>
  );
}


