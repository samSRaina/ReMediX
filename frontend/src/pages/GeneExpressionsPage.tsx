import { Tab, TabGroup, TabList, TabPanel, TabPanels } from '@headlessui/react';
import { Activity, Loader2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { AppLayout, Surface } from '../components/Layout';
import { getExcelMeta, getExcelSheetPage } from '../lib/api';
import type { ExcelMetaResponse, ExcelSheetResponse } from '../types/api';

export function GeneExpressionsPage() {
  const [meta, setMeta] = useState<ExcelMetaResponse | null>(null);
  const [activeSheet, setActiveSheet] = useState('');
  const [sheetPage, setSheetPage] = useState<ExcelSheetResponse | null>(null);
  const [loadingMeta, setLoadingMeta] = useState(false);
  const [loadingSheet, setLoadingSheet] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchInputBySheet, setSearchInputBySheet] = useState<Record<string, string>>({});
  const [searchBySheet, setSearchBySheet] = useState<Record<string, string>>({});
  const [pageBySheet, setPageBySheet] = useState<Record<string, number>>({});
  const [pageSizeBySheet, setPageSizeBySheet] = useState<Record<string, number>>({});

  useEffect(() => {
    async function loadMeta() {
      setLoadingMeta(true);
      setError(null);
      try {
        const payload = await getExcelMeta();
        setMeta(payload);

        const firstSheet = payload.sheetNames[0] ?? '';
        setActiveSheet(firstSheet);

        const initialPageBySheet: Record<string, number> = {};
        const initialPageSizeBySheet: Record<string, number> = {};
        const initialSearchBySheet: Record<string, string> = {};
        const initialSearchInputBySheet: Record<string, string> = {};

        payload.sheetNames.forEach((name) => {
          initialPageBySheet[name] = 1;
          initialPageSizeBySheet[name] = 50;
          initialSearchBySheet[name] = '';
          initialSearchInputBySheet[name] = '';
        });

        setPageBySheet(initialPageBySheet);
        setPageSizeBySheet(initialPageSizeBySheet);
        setSearchBySheet(initialSearchBySheet);
        setSearchInputBySheet(initialSearchInputBySheet);
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
        const payload = await getExcelSheetPage(
          activeSheet,
          pageBySheet[activeSheet] ?? 1,
          pageSizeBySheet[activeSheet] ?? 50,
        );
        setSheetPage(payload);
      } catch (err) {
        setSheetPage(null);
        setError(err instanceof Error ? err.message : 'Failed to load sheet data');
      } finally {
        setLoadingSheet(false);
      }
    }
    void loadSheet();
  }, [activeSheet, pageBySheet, pageSizeBySheet]);

  const filteredRows = useMemo(() => {
    if (!sheetPage) return [];
    const query = (searchBySheet[activeSheet] ?? '').trim().toLowerCase();
    if (!query) return sheetPage.data;
    return sheetPage.data.filter((row) =>
      row.some((cell) => String(cell ?? '').toLowerCase().includes(query)),
    );
  }, [activeSheet, searchBySheet, sheetPage]);

  const activeSearchInput = searchInputBySheet[activeSheet] ?? '';
  const activeSearchValue = searchBySheet[activeSheet] ?? '';
  const activePageSize = pageSizeBySheet[activeSheet] ?? 50;

  return (
    <AppLayout title="Gene Expressions" subtitle="Explore gene-expression Excel sheets">
      <Surface>
        {loadingMeta ? (
          <div className="flex items-center gap-2 p-6 text-sm text-slate-600">
            <Loader2 className="animate-spin" size={16} />
            Loading sheets...
          </div>
        ) : error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
        ) : !meta || meta.sheetNames.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 px-4 py-6 text-sm text-slate-500">
            No gene expression sheets available.
          </div>
        ) : (
          <TabGroup
            selectedIndex={Math.max(
              0,
              meta.sheetNames.findIndex((name) => name === activeSheet),
            )}
            onChange={(index) => setActiveSheet(meta.sheetNames[index] ?? '')}
          >
            <TabList className="flex flex-wrap gap-2 border-b border-slate-200 pb-4">
              {meta.sheetNames.map((name) => (
                <Tab
                  key={name}
                  className="inline-flex items-center gap-2 rounded-xl border border-transparent px-3 py-2 text-sm font-medium transition data-[selected]:border-cyan-600 data-[selected]:bg-cyan-600 data-[selected]:text-white data-[hover]:bg-slate-100"
                >
                  <Activity size={14} />
                  {name}
                </Tab>
              ))}
            </TabList>

            <TabPanels className="pt-5">
              {meta.sheetNames.map((name) => (
                <TabPanel key={name}>
                  <div className="grid gap-4 md:grid-cols-[2fr_1fr_1fr] md:items-end">
                    <label className="space-y-2">
                      <span className="text-sm font-medium">Search this sheet</span>
                      <input
                        value={name === activeSheet ? activeSearchInput : searchInputBySheet[name] ?? ''}
                        onChange={(event) =>
                          setSearchInputBySheet((prev) => ({ ...prev, [name]: event.target.value }))
                        }
                        onKeyDown={(event) => {
                          if (event.key === 'Enter') {
                            event.preventDefault();
                            setSearchBySheet((prev) => ({ ...prev, [name]: (searchInputBySheet[name] ?? '').trim() }));
                            setPageBySheet((prev) => ({ ...prev, [name]: 1 }));
                          }
                        }}
                        className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none ring-cyan-400 transition focus:border-cyan-400 focus:ring"
                        placeholder="Filter rows by any cell value"
                      />
                    </label>

                    <button
                      type="button"
                      className="rounded-xl bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm shadow-cyan-600/30 transition hover:-translate-y-0.5 hover:bg-cyan-500"
                      onClick={() => {
                        setSearchBySheet((prev) => ({ ...prev, [name]: (searchInputBySheet[name] ?? '').trim() }));
                        setPageBySheet((prev) => ({ ...prev, [name]: 1 }));
                      }}
                    >
                      Search
                    </button>

                    <button
                      type="button"
                      className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:-translate-y-0.5 hover:border-cyan-300 hover:bg-cyan-50"
                      onClick={() => {
                        setSearchInputBySheet((prev) => ({ ...prev, [name]: '' }));
                        setSearchBySheet((prev) => ({ ...prev, [name]: '' }));
                        setPageBySheet((prev) => ({ ...prev, [name]: 1 }));
                      }}
                    >
                      Clear
                    </button>
                  </div>

                  <div className="mt-4 flex items-center justify-between text-sm text-slate-600">
                    <span>
                      {sheetPage && name === activeSheet
                        ? `Showing ${Math.max(1, (sheetPage.page - 1) * sheetPage.pageSize + 1)}–${Math.min(sheetPage.page * sheetPage.pageSize, sheetPage.total)} of ${sheetPage.total.toLocaleString()}`
                        : 'No results'}
                    </span>
                    <label className="inline-flex items-center gap-2">
                      Rows per page
                      <select
                        value={name === activeSheet ? activePageSize : pageSizeBySheet[name] ?? 50}
                        onChange={(event) => {
                          const next = Number(event.target.value);
                          setPageSizeBySheet((prev) => ({ ...prev, [name]: next }));
                          setPageBySheet((prev) => ({ ...prev, [name]: 1 }));
                        }}
                        className="rounded-lg border border-slate-300 bg-white px-2 py-1"
                      >
                        {[25, 50, 100].map((n) => (
                          <option key={n} value={n}>
                            {n}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>

                  <div className="table-shell mt-4">
                    {loadingSheet && name === activeSheet ? (
                      <div className="flex items-center gap-2 p-6 text-sm text-slate-600">
                        <Loader2 className="animate-spin" size={16} />
                        Loading sheet...
                      </div>
                    ) : !sheetPage || name !== activeSheet || filteredRows.length === 0 ? (
                      <div className="p-6 text-sm text-slate-500">
                        {activeSearchValue
                          ? 'No rows match the current search.'
                          : 'No data available for this sheet.'}
                      </div>
                    ) : (
                      <table className="table-ui">
                        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                          <tr>
                            {sheetPage.headers.map((header, idx) => (
                              <th key={`${String(header ?? '')}-${idx}`} className="px-3 py-2">
                                {String(header ?? '-')}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {filteredRows.map((row, rowIdx) => (
                            <tr key={`${name}-row-${rowIdx}`}>
                              {sheetPage.headers.map((_, cellIdx) => (
                                <td key={`${name}-${rowIdx}-${cellIdx}`} className="px-3 py-2">
                                  {String(row[cellIdx] ?? '-')}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>

                  {sheetPage && name === activeSheet && sheetPage.totalPages > 1 ? (
                    <div className="mt-4 flex items-center justify-center gap-2">
                      <button
                        className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm transition hover:border-cyan-300 hover:bg-cyan-50 disabled:opacity-50"
                        disabled={sheetPage.page <= 1}
                        onClick={() => setPageBySheet((prev) => ({ ...prev, [name]: Math.max(1, sheetPage.page - 1) }))}
                      >
                        Prev
                      </button>
                      <span className="text-sm text-slate-600">
                        Page {sheetPage.page} / {sheetPage.totalPages}
                      </span>
                      <button
                        className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm transition hover:border-cyan-300 hover:bg-cyan-50 disabled:opacity-50"
                        disabled={sheetPage.page >= sheetPage.totalPages}
                        onClick={() =>
                          setPageBySheet((prev) => ({ ...prev, [name]: Math.min(sheetPage.totalPages, sheetPage.page + 1) }))
                        }
                      >
                        Next
                      </button>
                    </div>
                  ) : null}
                </TabPanel>
              ))}
            </TabPanels>
          </TabGroup>
        )}
      </Surface>
    </AppLayout>
  );
}


