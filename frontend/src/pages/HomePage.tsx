import { Tab, TabGroup, TabList, TabPanel, TabPanels } from '@headlessui/react';
import { Activity, Clipboard, FlaskConical, Loader2, Search, TestTube2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import type { ChangeEvent, FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { getBioactivityByInchiKey, getCompoundByName, getCompoundBySmile, getDrugBankByInchiKey } from '../lib/api';
import type { BioactivityRecord, DrugBankData, PubChemCompound } from '../types/api';
import { AppLayout, Surface } from '../components/Layout';

type SortKey = keyof BioactivityRecord;
type SortDirection = 'asc' | 'desc';

const BIOACTIVITY_COLUMNS: Array<{ key: SortKey; label: string }> = [
  { key: 'target_chembl_id', label: 'Target ChEMBL ID' },
  { key: 'target_name', label: 'Target Name' },
  { key: 'target_type', label: 'Target Type' },
  { key: 'target_organism', label: 'Organism' },
  { key: 'gene_symbol', label: 'Gene Symbol' },
  { key: 'uniprot_id', label: 'UniProt ID' },
  { key: 'standard_type', label: 'Standard Type' },
  { key: 'standard_value', label: 'Standard Value' },
  { key: 'standard_units', label: 'Units' },
  { key: 'protein_target_classification', label: 'Protein Class' },
];

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '--';
  return String(value);
}

export function HomePage() {
  const [compoundInput, setCompoundInput] = useState('');
  const [searchBySmile, setSearchBySmile] = useState(false);
  const [pubchemData, setPubchemData] = useState<PubChemCompound | null>(null);
  const [drugbankData, setDrugbankData] = useState<DrugBankData | null>(null);
  const [bioactivityRows, setBioactivityRows] = useState<BioactivityRecord[]>([]);
  const [geneSet, setGeneSet] = useState<string[]>([]);
  const [bioactivityType, setBioactivityType] = useState<'IC50' | 'AC50' | 'Ki'>('IC50');
  const [bioFilter, setBioFilter] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('target_chembl_id');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const [isSearching, setIsSearching] = useState(false);
  const [isLoadingBioactivity, setIsLoadingBioactivity] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const currentInchiKey = pubchemData?.InChIKey ?? '';

  useEffect(() => {
    if (!currentInchiKey) return;
    async function refreshBioactivity() {
      setIsLoadingBioactivity(true);
      try {
        const payload = await getBioactivityByInchiKey(currentInchiKey, bioactivityType);
        setBioactivityRows(payload.activities ?? []);
        setGeneSet(payload.gene_set ?? []);
      } catch (error) {
        setBioactivityRows([]);
        setGeneSet([]);
        setErrorMessage(error instanceof Error ? error.message : 'Failed to load bioactivity');
      } finally {
        setIsLoadingBioactivity(false);
      }
    }
    void refreshBioactivity();
  }, [bioactivityType, currentInchiKey]);

  const filteredSortedBioactivity = useMemo(() => {
    const query = bioFilter.trim().toLowerCase();
    const filtered = query
      ? bioactivityRows.filter((row) =>
          [row.target_name, row.gene_symbol, row.uniprot_id, row.target_chembl_id].join(' ').toLowerCase().includes(query),
        )
      : bioactivityRows;

    return [...filtered].sort((a, b) => {
      const left = String(a[sortKey] ?? '').toLowerCase();
      const right = String(b[sortKey] ?? '').toLowerCase();
      if (left === right) return 0;
      return sortDirection === 'asc' ? (left > right ? 1 : -1) : left > right ? -1 : 1;
    });
  }, [bioactivityRows, bioFilter, sortKey, sortDirection]);

  function onSortChange(nextKey: SortKey) {
    if (sortKey === nextKey) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setSortKey(nextKey);
    setSortDirection('asc');
  }

  async function handleSearch(event: FormEvent) {
    event.preventDefault();
    if (!compoundInput.trim()) {
      setErrorMessage('Please enter a compound name or SMILES string.');
      return;
    }

    setErrorMessage(null);
    setIsSearching(true);
    setPubchemData(null);
    setDrugbankData(null);
    setBioactivityRows([]);
    setGeneSet([]);

    try {
      const compound = searchBySmile ? await getCompoundBySmile(compoundInput.trim()) : await getCompoundByName(compoundInput.trim());
      setPubchemData(compound);

      const inchiKey = compound.InChIKey;
      if (!inchiKey) return;

      const [drugbankPayload, bioactivityPayload] = await Promise.allSettled([
        getDrugBankByInchiKey(inchiKey),
        getBioactivityByInchiKey(inchiKey, bioactivityType),
      ]);

      if (drugbankPayload.status === 'fulfilled') setDrugbankData(drugbankPayload.value);
      if (bioactivityPayload.status === 'fulfilled') {
        setBioactivityRows(bioactivityPayload.value.activities ?? []);
        setGeneSet(bioactivityPayload.value.gene_set ?? []);
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Search failed');
    } finally {
      setIsSearching(false);
    }
  }

  return (
    <AppLayout title="VascuMap Explorer" subtitle="Modernized biomedical discovery interface">
      <Surface>
        <form className="grid gap-4" onSubmit={handleSearch}>
          <div className="rounded-xl border border-cyan-100 bg-cyan-50/60 px-4 py-3 text-sm text-cyan-900">
            Search a compound by name or SMILES, then open matching genes for disease-level directional analysis.
          </div>
          <label className="space-y-2">
            <span className="text-sm font-medium">Compound Lookup</span>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
              <input
                value={compoundInput}
                onChange={(event: ChangeEvent<HTMLInputElement>) => setCompoundInput(event.target.value)}
                placeholder={searchBySmile ? 'CC(=O)OC1=CC=CC=C1C(=O)O' : 'Aspirin'}
                className="w-full rounded-xl border border-slate-300 bg-white py-2.5 pl-9 pr-3 text-sm outline-none ring-cyan-400 transition focus:border-cyan-400 focus:ring"
              />
            </div>
          </label>

          <div className="flex flex-wrap items-center gap-3">
            <label className="inline-flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-slate-300"
                checked={searchBySmile}
                onChange={(event: ChangeEvent<HTMLInputElement>) => setSearchBySmile(event.target.checked)}
              />
              Search by SMILES
            </label>

            <button
              type="submit"
              disabled={isSearching}
                className="inline-flex items-center gap-2 rounded-xl bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm shadow-cyan-600/30 transition hover:-translate-y-0.5 hover:bg-cyan-500 disabled:opacity-50"
            >
              {isSearching ? <Loader2 className="animate-spin" size={16} /> : <FlaskConical size={16} />}
              {isSearching ? 'Searching...' : 'Fetch Compound Profile'}
            </button>

            {geneSet.length > 0 ? (
              <Link
                to={`/geneMatch?genes=${encodeURIComponent(geneSet.join(','))}`}
                className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium transition hover:-translate-y-0.5 hover:border-cyan-300 hover:bg-cyan-50"
              >
                Open Gene Match ({geneSet.length})
              </Link>
            ) : null}
          </div>
        </form>

        {errorMessage ? <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{errorMessage}</div> : null}
      </Surface>

      <Surface>
        <TabGroup>
          <TabList className="flex flex-wrap gap-2 border-b border-slate-200 pb-4">
            {[{ title: 'Chemical Identity', icon: TestTube2 }, { title: 'Curated Pharmacology', icon: Clipboard }, { title: 'Bioactivity', icon: Activity }].map(
              ({ title, icon: Icon }) => (
                <Tab
                  key={title}
                  className="inline-flex items-center gap-2 rounded-xl border border-transparent px-3 py-2 text-sm font-medium transition data-[selected]:border-cyan-600 data-[selected]:bg-cyan-600 data-[selected]:text-white data-[hover]:bg-slate-100"
                >
                  <Icon size={16} />
                  {title}
                </Tab>
              ),
            )}
          </TabList>

          <TabPanels className="pt-5">
            <TabPanel>
              {!pubchemData ? (
                <p className="rounded-xl border border-dashed border-slate-300 p-6 text-sm text-slate-500">No compound loaded yet.</p>
              ) : (
                <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {Object.entries(pubchemData).map(([key, value]) => (
                    <div key={key} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                      <dt className="text-xs uppercase tracking-wide text-slate-500">{key}</dt>
                      <dd className="mt-1 text-sm font-medium">{formatValue(value)}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </TabPanel>

            <TabPanel>
              {!drugbankData ? (
                <p className="rounded-xl border border-dashed border-slate-300 p-6 text-sm text-slate-500">No curated pharmacology returned for this compound.</p>
              ) : (
                <dl className="grid gap-4">
                  <div className="rounded-xl border border-slate-200 p-4"><dt className="text-xs uppercase tracking-wide text-slate-500">Groups</dt><dd className="mt-2 text-sm">{(drugbankData.groups ?? []).join(', ') || '--'}</dd></div>
                  <div className="rounded-xl border border-slate-200 p-4"><dt className="text-xs uppercase tracking-wide text-slate-500">Indications</dt><dd className="mt-2 text-sm">{formatValue(drugbankData.indication)}</dd></div>
                  <div className="rounded-xl border border-slate-200 p-4"><dt className="text-xs uppercase tracking-wide text-slate-500">Targets</dt><dd className="mt-2 text-sm">{(drugbankData.targets ?? []).join(', ') || '--'}</dd></div>
                </dl>
              )}
            </TabPanel>

            <TabPanel>
              <div className="mb-4 flex flex-wrap items-center gap-3">
                {(['IC50', 'AC50', 'Ki'] as const).map((type) => (
                  <button
                    key={type}
                    type="button"
                    onClick={() => setBioactivityType(type)}
                    className={`rounded-xl px-3 py-2 text-xs font-semibold transition ${
                      bioactivityType === type
                        ? 'bg-cyan-600 text-white shadow-sm shadow-cyan-600/30'
                        : 'border border-slate-300 bg-white hover:border-cyan-300 hover:bg-cyan-50'
                    }`}
                  >
                    {type}
                  </button>
                ))}
                <input
                  value={bioFilter}
                  onChange={(event: ChangeEvent<HTMLInputElement>) => setBioFilter(event.target.value)}
                  placeholder="Filter by target, gene, UniProt, ChEMBL ID"
                  className="min-w-[280px] flex-1 rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm outline-none ring-cyan-400 transition focus:border-cyan-400 focus:ring"
                />
              </div>

              {isLoadingBioactivity ? (
                <div className="flex items-center gap-2 rounded-xl border border-dashed border-slate-300 p-6 text-sm"><Loader2 className="animate-spin" size={16} />Loading bioactivity data...</div>
              ) : filteredSortedBioactivity.length === 0 ? (
                <p className="rounded-xl border border-dashed border-slate-300 p-6 text-sm text-slate-500">No bioactivity rows match the current filter.</p>
              ) : (
                <div className="table-shell">
                  <table className="table-ui divide-y divide-slate-200">
                    <thead className="bg-slate-50">
                      <tr>
                        {BIOACTIVITY_COLUMNS.map((column) => (
                          <th key={column.key} className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                            <button type="button" onClick={() => onSortChange(column.key)} className="inline-flex items-center gap-1 hover:text-cyan-600">
                              {column.label}
                              {sortKey === column.key ? (sortDirection === 'asc' ? '↑' : '↓') : ''}
                            </button>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {filteredSortedBioactivity.map((row, index) => (
                        <tr key={`${row.target_chembl_id}-${row.gene_symbol}-${index}`}>
                          {BIOACTIVITY_COLUMNS.map((column) => (
                            <td key={column.key} className="whitespace-nowrap px-3 py-2">{formatValue(row[column.key])}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </TabPanel>
          </TabPanels>
        </TabGroup>
      </Surface>
    </AppLayout>
  );
}

