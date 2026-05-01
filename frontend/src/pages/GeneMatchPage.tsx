import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { AppLayout, Surface } from '../components/Layout';
import { SourceBadges } from '../components/SourceBadges';
import { getDiseaseSignatureTable, getDiseases, getFinalGeneScore, getGeneMatch } from '../lib/api';
import type { DiseaseSignatureTableResponse, FinalGeneScoreResponse, GeneMatchItem } from '../types/api';

function getUpCount(row: GeneMatchItem): number {
  return row.up_count ?? row.total_up ?? 0;
}

function getDownCount(row: GeneMatchItem): number {
  return row.down_count ?? row.total_down ?? 0;
}

export function GeneMatchPage() {
  const [searchParams] = useSearchParams();
  const genes = useMemo(() => (searchParams.get('genes') || '').split(',').map((g: string) => g.trim()).filter(Boolean), [searchParams]);
  const initialDisease = (searchParams.get('disease') || '').trim();

  const [disease, setDisease] = useState(initialDisease);
  const [diseases, setDiseases] = useState<string[]>([]);
  const [matchResults, setMatchResults] = useState<GeneMatchItem[]>([]);
  const [score, setScore] = useState<FinalGeneScoreResponse | null>(null);
  const [table, setTable] = useState<DiseaseSignatureTableResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [tableLoading, setTableLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadDiseases() {
      try {
        const payload = await getDiseases();
        setDiseases(payload.diseases || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load diseases');
      }
    }
    void loadDiseases();
  }, []);

  useEffect(() => {
    if (!disease) {
      setTable(null);
      return;
    }
    let cancelled = false;
    async function loadTable() {
      setTableLoading(true);
      try {
        const firstPage = await getDiseaseSignatureTable(disease, 1, 100);
        if (cancelled) return;

        if (!firstPage.totalPages || firstPage.totalPages <= 1) {
          setTable(firstPage);
          return;
        }

        const pendingPages: Promise<DiseaseSignatureTableResponse>[] = [];
        for (let page = 2; page <= firstPage.totalPages; page += 1) {
          pendingPages.push(getDiseaseSignatureTable(disease, page, 100));
        }

        const remainingPages = await Promise.all(pendingPages);
        if (cancelled) return;

        setTable({
          ...firstPage,
          data: [firstPage.data, ...remainingPages.map((payload) => payload.data)].flat(),
          page: 1,
          totalPages: 1,
          pageSize: firstPage.total,
        });
      } catch (err) {
        if (!cancelled) {
          setTable(null);
          setError(err instanceof Error ? err.message : 'Failed to load disease signature table');
        }
      } finally {
        if (!cancelled) {
          setTableLoading(false);
        }
      }
    }
    void loadTable();

    return () => {
      cancelled = true;
    };
  }, [disease]);

  async function runMatch() {
    if (!disease || genes.length === 0) return;
    setLoading(true);
    setError(null);
    setScore(null);
    try {
      const payload = await getGeneMatch(genes.join(','), disease);
      setMatchResults(payload.results || []);
    } catch (err) {
      setMatchResults([]);
      setError(err instanceof Error ? err.message : 'Failed to run match');
    } finally {
      setLoading(false);
    }
  }

  async function calculateScore() {
    if (!disease || genes.length === 0) return;
    setLoading(true);
    setError(null);
    try {
      const payload = await getFinalGeneScore(genes.join(','), disease);
      setScore(payload);
    } catch (err) {
      setScore(null);
      setError(err instanceof Error ? err.message : 'Failed to calculate score');
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppLayout title="Directional Therapeutic Effect" subtitle="Match compound-linked genes against disease signatures">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold text-slate-900">Directional Therapeutic Effect</h1>
        <p className="text-sm text-slate-600">Match compound-linked genes against disease signatures</p>
      </div>
      <Surface>
        <div className="grid gap-4 md:grid-cols-[2fr_1fr_1fr] md:items-end">
          <label className="space-y-2">
            <span className="text-sm font-medium">Target Disease</span>
            <input
              value={disease}
              onChange={(event) => setDisease(event.target.value)}
              list="disease-list"
              placeholder="Select or type a disease"
              className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none ring-cyan-400 transition focus:border-cyan-400 focus:ring"
            />
            <datalist id="disease-list">
              {diseases.map((d) => (
                <option key={d} value={d} />
              ))}
            </datalist>
          </label>

          <button
            type="button"
            onClick={() => void runMatch()}
            disabled={loading || !disease || genes.length === 0}
            className="rounded-xl bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm shadow-cyan-600/30 transition hover:-translate-y-0.5 hover:bg-cyan-500 disabled:opacity-50"
          >
            Run Match
          </button>
          <button
            type="button"
            onClick={() => void calculateScore()}
            disabled={loading || !disease || genes.length === 0 || matchResults.length === 0}
            className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:-translate-y-0.5 hover:border-cyan-300 hover:bg-cyan-50 disabled:opacity-50"
          >
            Get Score
          </button>
        </div>

        <details className="mt-3 rounded-xl border border-slate-200 bg-slate-50/80 px-4 py-3 text-sm text-slate-600">
          <summary className="cursor-pointer font-semibold text-slate-700">Gene set ({genes.length})</summary>
          <div className="mt-2">
            {genes.length > 0 ? genes.join(', ') : '(none provided)'}
          </div>
        </details>

        {score ? (
          <div className="mt-4 rounded-xl border border-cyan-200 bg-cyan-50 p-4">
            <p className="text-sm font-semibold text-cyan-900">Re-purposing Score</p>
            <p className="text-2xl font-bold text-cyan-800">{score.score.toFixed(6)}</p>
            <p className="text-xs text-cyan-700">Based on {score.genes_counted?.length ?? 0} classified genes</p>
          </div>
        ) : null}

        {error ? <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div> : null}
      </Surface>

      <div className="grid gap-6 lg:grid-cols-2">
        <Surface>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600">Match Results</h2>
            <SourceBadges sourceKeys={['creeds']} />
          </div>
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-slate-600"><Loader2 className="animate-spin" size={16} />Matching genes...</div>
          ) : matchResults.length === 0 ? (
            <p className="rounded-xl border border-dashed border-slate-300 p-6 text-sm text-slate-500">No match results yet.</p>
          ) : (
            <div className="table-shell">
              <table className="table-ui">
                <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-3 py-2">Gene</th>
                    <th className="px-3 py-2">Total Up</th>
                    <th className="px-3 py-2">Total Down</th>
                    <th className="px-3 py-2">Ratio</th>
                    <th className="px-3 py-2">Direction</th>
                  </tr>
                </thead>
                <tbody>
                  {matchResults.map((row) => (
                    <tr key={row.gene}>
                      <td className="px-3 py-2 font-medium">{row.gene}</td>
                      <td className="px-3 py-2 text-emerald-700">{getUpCount(row)}</td>
                      <td className="px-3 py-2 text-rose-700">{getDownCount(row)}</td>
                      <td className="px-3 py-2">{typeof row.ratio === 'number' ? row.ratio.toFixed(3) : 'N/A'}</td>
                      <td className="px-3 py-2">{row.direction ?? row.classification ?? row.error ?? 'N/A'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Surface>

        <Surface>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600">Disease Signature Table</h2>
            <SourceBadges sourceKeys={['creeds']} />
          </div>
          {tableLoading ? (
            <div className="flex items-center gap-2 text-sm text-slate-600"><Loader2 className="animate-spin" size={16} />Loading disease signature...</div>
          ) : !table || !table.data || table.data.length === 0 ? (
            <p className="rounded-xl border border-dashed border-slate-300 p-6 text-sm text-slate-500">No disease signature data loaded.</p>
          ) : (
            <div className="table-shell">
              <table className="table-ui">
                <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                  <tr>{table.headers.map((h: string) => <th key={h} className="px-3 py-2">{h}</th>)}</tr>
                </thead>
                <tbody>
                  {table.data.map((row: Array<string | number>, idx: number) => (
                    <tr key={`${row[0]}-${idx}`}>
                      {row.map((cell: string | number, cidx: number) => <td key={`${idx}-${cidx}`} className="px-3 py-2">{String(cell)}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Surface>
      </div>
    </AppLayout>
  );
}
