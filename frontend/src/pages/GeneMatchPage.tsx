import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { AppLayout, Surface } from '../components/Layout';
import { SourceBadges } from '../components/SourceBadges';
import { getDiseaseSignatureTable, getDiseases, getRemedixScore } from '../lib/api';
import type { DiseaseSignatureTableResponse, RemedixGeneRecord, RemedixScoringSummary } from '../types/api';

function formatPct(value: number): string {
  return `${value.toFixed(2)}%`;
}

export function GeneMatchPage() {
  const [searchParams] = useSearchParams();
  const genes = useMemo(() => (searchParams.get('genes') || '').split(',').map((g: string) => g.trim()).filter(Boolean), [searchParams]);
  const initialDisease = (searchParams.get('disease') || '').trim();
  const inchikey = (searchParams.get('inchikey') || '').trim();

  const [disease, setDisease] = useState(initialDisease);
  const [diseases, setDiseases] = useState<string[]>([]);
  const [score, setScore] = useState<RemedixScoringSummary | null>(null);
  const [geneRecords, setGeneRecords] = useState<RemedixGeneRecord[]>([]);
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

  async function runScoring() {
    if (!disease || !inchikey) return;
    setLoading(true);
    setError(null);
    try {
      const payload = await getRemedixScore(inchikey, disease);
      setScore(payload.scoring);
      setGeneRecords(payload.scoring.gene_records ?? []);
    } catch (err) {
      setScore(null);
      setGeneRecords([]);
      setError(err instanceof Error ? err.message : 'Failed to run ReMediX scoring');
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppLayout title="Directional Therapeutic Effect" subtitle="Compute disease-aligned ReMediX scoring with directional consensus">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold text-slate-900">Directional Therapeutic Effect</h1>
        <p className="text-sm text-slate-600">Drug–disease alignment using CREEDS consensus and ChEMBL bioactivity strength</p>
      </div>
      <Surface>
        <div className="grid gap-4 md:grid-cols-[2fr_1fr] md:items-end">
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
            onClick={() => void runScoring()}
            disabled={loading || !disease || !inchikey}
            className="rounded-xl bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm shadow-cyan-600/30 transition hover:-translate-y-0.5 hover:bg-cyan-500 disabled:opacity-50"
          >
            Run ReMediX Scoring
          </button>
        </div>

        <details className="mt-3 rounded-xl border border-slate-200 bg-slate-50/80 px-4 py-3 text-sm text-slate-600">
          <summary className="cursor-pointer font-semibold text-slate-700">Input context</summary>
          <div className="mt-2 space-y-1">
            <p><span className="font-medium">InChIKey:</span> {inchikey || '(missing)'}</p>
            <p><span className="font-medium">Gene set from ChEMBL page:</span> {genes.length > 0 ? genes.join(', ') : '(none provided)'}</p>
          </div>
        </details>

        {!inchikey ? (
          <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            InChIKey is missing. Start from the home page to run consolidated ReMediX scoring.
          </div>
        ) : null}

        {score ? (
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-cyan-200 bg-cyan-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-cyan-900">ReMediX Score</p>
              <p className="text-2xl font-bold text-cyan-800">{score.remedix_score.toFixed(3)}</p>
              <p className="text-xs text-cyan-700">Raw: {score.raw_remedix_score.toFixed(3)}</p>
            </div>
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-emerald-900">Beneficial Signal</p>
              <p className="text-xl font-bold text-emerald-800">{score.beneficial_signal.toFixed(3)}</p>
              <p className="text-xs text-emerald-700">Coverage: {formatPct(score.benefit_coverage_percent)}</p>
            </div>
            <div className="rounded-xl border border-rose-200 bg-rose-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-rose-900">Harmful Signal</p>
              <p className="text-xl font-bold text-rose-800">{score.harmful_signal.toFixed(3)}</p>
              <p className="text-xs text-rose-700">Burden: {formatPct(score.harm_coverage_percent)}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-700">Net Therapeutic Signal</p>
              <p className="text-xl font-bold text-slate-900">{score.net_therapeutic_signal.toFixed(3)}</p>
              <p className="text-xs text-slate-600">Target coverage: {formatPct(score.target_coverage_percent)}</p>
            </div>
          </div>
        ) : null}

        {error ? <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div> : null}
      </Surface>

      <div className="grid gap-6 lg:grid-cols-2">
        <Surface>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600">Gene-level Traceability</h2>
            <SourceBadges sourceKeys={['chembl', 'uniprot', 'creeds']} />
          </div>
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-slate-600"><Loader2 className="animate-spin" size={16} />Scoring genes...</div>
          ) : geneRecords.length === 0 ? (
            <p className="rounded-xl border border-dashed border-slate-300 p-6 text-sm text-slate-500">No scored gene records yet.</p>
          ) : (
            <div className="table-shell">
              <table className="table-ui">
                <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-3 py-2">Gene</th>
                    <th className="px-3 py-2">U</th>
                    <th className="px-3 py-2">D</th>
                    <th className="px-3 py-2">DC</th>
                    <th className="px-3 py-2">Disease Dir</th>
                    <th className="px-3 py-2">Drug Action</th>
                    <th className="px-3 py-2">Activity Strength</th>
                    <th className="px-3 py-2">Class</th>
                    <th className="px-3 py-2">Contribution</th>
                  </tr>
                </thead>
                <tbody>
                  {geneRecords.map((row) => (
                    <tr key={row.gene}>
                      <td className="px-3 py-2 font-medium">{row.gene}</td>
                      <td className="px-3 py-2">{row.U}</td>
                      <td className="px-3 py-2">{row.D}</td>
                      <td className="px-3 py-2">{row.dc.toFixed(3)}</td>
                      <td className="px-3 py-2">{row.disease_direction}</td>
                      <td className="px-3 py-2">{row.drug_action}</td>
                      <td className="px-3 py-2">{row.activity_strength.toFixed(3)}</td>
                      <td className="px-3 py-2">{row.classification}</td>
                      <td className="px-3 py-2">{row.gene_contribution.toFixed(3)}</td>
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
