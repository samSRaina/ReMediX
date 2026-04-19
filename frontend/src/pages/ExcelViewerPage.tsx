import { Loader2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { AppLayout, Surface } from '../components/Layout';
import { getExcelMeta, getExcelSheetPage } from '../lib/api';
import type { ExcelMetaResponse, ExcelSheetResponse } from '../types/api';

const PAGE_SIZE = 100;

export function ExcelViewerPage() {
  const [meta, setMeta] = useState<ExcelMetaResponse | null>(null);
  const [activeSheet, setActiveSheet] = useState<string>('');
  const [sheetPage, setSheetPage] = useState<ExcelSheetResponse | null>(null);
  const [loadingMeta, setLoadingMeta] = useState(false);
  const [loadingSheet, setLoadingSheet] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pageBySheet, setPageBySheet] = useState<Record<string, number>>({});

  useEffect(() => {
    async function loadMeta() {
      setLoadingMeta(true);
      setError(null);
      try {
        const payload = await getExcelMeta();
        setMeta(payload);
        const first = payload.sheetNames[0] || '';
        setActiveSheet(first);
        const initState: Record<string, number> = {};
        payload.sheetNames.forEach((s: string) => (initState[s] = 1));
        setPageBySheet(initState);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load sheet metadata');
      } finally {
        setLoadingMeta(false);
      }
    }
    void loadMeta();
  }, []);

  useEffect(() => {
    if (!activeSheet) return;
    async function loadSheet() {
      setLoadingSheet(true);
      setError(null);
      try {
        const page = pageBySheet[activeSheet] || 1;
        const payload = await getExcelSheetPage(activeSheet, page, PAGE_SIZE);
        setSheetPage(payload);
      } catch (err) {
        setSheetPage(null);
        setError(err instanceof Error ? err.message : 'Failed to load sheet page');
      } finally {
        setLoadingSheet(false);
      }
    }
    void loadSheet();
  }, [activeSheet, pageBySheet]);

  return (
    <AppLayout title="Disease Molecular Signature" subtitle="Explore all non-Reactome sheets from the dataset">
      <Surface>
        {loadingMeta ? (
          <div className="flex items-center gap-2 text-sm text-slate-600"><Loader2 className="animate-spin" size={16} />Loading sheets...</div>
        ) : error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
        ) : !meta || meta.sheetNames.length === 0 ? (
          <p className="text-sm text-slate-500">No sheets available.</p>
        ) : (
          <>
            <div className="mb-4 flex flex-wrap gap-2">
              {meta.sheetNames.map((name: string) => (
                <button
                  key={name}
                  type="button"
                  onClick={() => setActiveSheet(name)}
                  className={`rounded-xl px-3 py-2 text-sm font-medium transition ${
                    activeSheet === name
                      ? 'bg-cyan-600 text-white shadow-sm shadow-cyan-600/30'
                      : 'border border-slate-300 bg-white hover:-translate-y-0.5 hover:border-cyan-300 hover:bg-cyan-50'
                  }`}
                >
                  {name.trim()}
                </button>
              ))}
            </div>

            {loadingSheet ? (
              <div className="flex items-center gap-2 text-sm text-slate-600"><Loader2 className="animate-spin" size={16} />Loading sheet data...</div>
            ) : !sheetPage ? (
              <p className="text-sm text-slate-500">No sheet data loaded.</p>
            ) : (
              <>
                <p className="mb-3 text-sm text-slate-600">
                  Showing {(sheetPage.page - 1) * sheetPage.pageSize + 1}–{Math.min(sheetPage.page * sheetPage.pageSize, sheetPage.total)} of {sheetPage.total.toLocaleString()} rows.
                </p>
                <div className="table-shell">
                  <table className="table-ui">
                    <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                      <tr>{sheetPage.headers.map((h: string | null, idx: number) => <th key={`${String(h)}-${idx}`} className="px-3 py-2">{String(h || '-')}</th>)}</tr>
                    </thead>
                    <tbody>
                      {sheetPage.data.map((row: Array<string | number | null>, rIdx: number) => (
                        <tr key={`r-${rIdx}`}>
                          {sheetPage.headers.map((_: string | null, cIdx: number) => <td key={`c-${rIdx}-${cIdx}`} className="px-3 py-2">{String(row[cIdx] ?? '-')}</td>)}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {sheetPage.totalPages > 1 ? (
                  <div className="mt-4 flex items-center justify-center gap-2">
                    <button
                      className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm transition hover:border-cyan-300 hover:bg-cyan-50 disabled:opacity-50"
                      disabled={sheetPage.page <= 1}
                      onClick={() => setPageBySheet((prev) => ({ ...prev, [activeSheet]: Math.max(1, sheetPage.page - 1) }))}
                    >
                      Prev
                    </button>
                    <span className="text-sm text-slate-600">Page {sheetPage.page} / {sheetPage.totalPages}</span>
                    <button
                      className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm transition hover:border-cyan-300 hover:bg-cyan-50 disabled:opacity-50"
                      disabled={sheetPage.page >= sheetPage.totalPages}
                      onClick={() => setPageBySheet((prev) => ({ ...prev, [activeSheet]: Math.min(sheetPage.totalPages, sheetPage.page + 1) }))}
                    >
                      Next
                    </button>
                  </div>
                ) : null}
              </>
            )}
          </>
        )}
      </Surface>
    </AppLayout>
  );
}


