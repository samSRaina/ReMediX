import { Tab, TabGroup, TabList, TabPanel, TabPanels } from '@headlessui/react';
import { Activity, Clipboard, FlaskConical, Loader2, Search, TestTube2 } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { ChangeEvent, FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { getBioactivityByInchiKey, getCompoundByName, getCompoundBySmile, getDrugBankByInchiKey } from '../lib/api';
import type { BioactivityRecord, DrugBankData, PubChemCompound } from '../types/api';
import { AppLayout } from '../components/Layout';
import { SourceBadges } from '../components/SourceBadges';

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

const NAME_PLACEHOLDER = 'Aspirin';
const SMILES_PLACEHOLDER = 'CC(=O)OC1=CC=CC=C1C(=O)O';
const SMILES_INVALID_PATTERN = /[.\[\]]/;
const CHEMICAL_IDENTITY_ORDER = [
  'CID',
  'CanonicalSMILES',
  'SMILES',
  'InChI',
  'InChIKey',
  'IUPACName',
  'MolecularFormula',
  'MolecularWeight',
  'XLogP',
  'HBondAcceptorCount',
  'HBondDonorCount',
  'TPSA',
];
const CHEMICAL_LABEL_OVERRIDES: Record<string, string> = {
  CID: 'CID',
  CanonicalSMILES: 'Canonical SMILES',
  SMILES: 'SMILES',
  InChI: 'InChI',
  InChIKey: 'InChIKey',
  IUPACName: 'IUPAC Name',
  MolecularFormula: 'Molecular Formula',
  MolecularWeight: 'Molecular Weight',
  XLogP: 'XLogP',
  HBondAcceptorCount: 'HBA',
  HBondDonorCount: 'HBD',
  TPSA: 'TPSA',
};

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '--';
  return String(value);
}

function formatFieldLabel(label: string): string {
  return label.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatIdentityLabel(label: string): string {
  return CHEMICAL_LABEL_OVERRIDES[label] ?? formatFieldLabel(label);
}

export function HomePage() {
  const [compoundInput, setCompoundInput] = useState('');
  const [searchBySmile, setSearchBySmile] = useState(false);
  const [smilesValidationInput, setSmilesValidationInput] = useState<string | null>(null);
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
  const workflowSectionRef = useRef<HTMLElement | null>(null);

  const currentInchiKey = pubchemData?.InChIKey ?? '';
  const isSmilesBlocked =
    searchBySmile && smilesValidationInput !== null && compoundInput.trim() === smilesValidationInput;
  const smilesValidationMessage = isSmilesBlocked
    ? `Unidentified chemistry class detected. Your input contains a salt form indicator (.) or metal complex notation ([ ]). Please enter a clean single-parent organic molecule.`
    : null;

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

  function handleCompoundInputChange(event: ChangeEvent<HTMLInputElement>) {
    const nextValue = event.target.value;
    setCompoundInput(nextValue);
    if (smilesValidationInput && nextValue.trim() !== smilesValidationInput) {
      setSmilesValidationInput(null);
    }
  }

  function handleSearchModeChange(nextMode: 'name' | 'smiles') {
    setSearchBySmile(nextMode === 'smiles');
    setSmilesValidationInput(null);
  }

  async function handleSearch(event: FormEvent) {
    event.preventDefault();
    const trimmedInput = compoundInput.trim();
    if (!trimmedInput) {
      setErrorMessage('Please enter a compound name or SMILES string.');
      return;
    }

    if (searchBySmile) {
      if (isSmilesBlocked) {
        return;
      }
      if (SMILES_INVALID_PATTERN.test(trimmedInput)) {
        setSmilesValidationInput(trimmedInput);
        return;
      }
    } else if (smilesValidationInput) {
      setSmilesValidationInput(null);
    }

    setErrorMessage(null);
    setIsSearching(true);
    setPubchemData(null);
    setDrugbankData(null);
    setBioactivityRows([]);
    setGeneSet([]);

    try {
      const compound = searchBySmile ? await getCompoundBySmile(trimmedInput) : await getCompoundByName(trimmedInput);
      if (!compound) {
        setErrorMessage('Compound not found in PubChem. Please try another name or SMILES string.');
        return;
      }
      setPubchemData(compound);

      const inchiKey = compound.InChIKey;
      if (!inchiKey) {
        setErrorMessage('PubChem response is missing InChIKey for this compound.');
        return;
      }

      // Do not block curated pharmacology behind ChEMBL loading.
      // Bioactivity is fetched by the currentInchiKey useEffect.
      try {
        const drugbankPayload = await getDrugBankByInchiKey(inchiKey);
        setDrugbankData(drugbankPayload);
      } catch {
        // DrugBank can legitimately miss some compounds; keep the rest of the workflow usable.
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Search failed');
    } finally {
      setIsSearching(false);
    }
  }

  function revealWorkflow() {
    workflowSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  const chemicalIdentityEntries = useMemo(() => {
    if (!pubchemData) return [];
    const entries = Object.entries(pubchemData);
    const entriesMap = new Map(entries);
    const orderedEntries = CHEMICAL_IDENTITY_ORDER.filter((key) => entriesMap.has(key)).map((key) => [
      key,
      entriesMap.get(key),
    ]);
    const orderedKeys = new Set(CHEMICAL_IDENTITY_ORDER);
    const remainingEntries = entries.filter(([key]) => !orderedKeys.has(key));
    return [...orderedEntries, ...remainingEntries];
  }, [pubchemData]);

  return (
    <AppLayout fullWidth title="ReMedix" subtitle="Map molecular signals to therapeutic direction">
      <section className="flex min-h-[calc(100vh-7rem)] items-center px-2 py-6 text-center sm:px-4 sm:py-10">
        <div className="mx-auto max-w-5xl">
          <h2 className="mt-4 text-5xl font-semibold tracking-tight text-slate-900 sm:text-6xl md:text-7xl">ReMediX</h2>
          <p className="mx-auto mt-5 max-w-3xl text-lg leading-relaxed text-slate-600 sm:text-xl">
            ReMediX scores any drug or compound for repurposing potential against any disease--integrating 8 databases, 5 analytical steps and a weighted molecular structure.
          </p>
          <div className="mt-7 flex flex-wrap items-center justify-center gap-3">
            <button
              type="button"
              onClick={revealWorkflow}
              className="rounded-xl bg-cyan-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm shadow-cyan-600/30 transition duration-200 hover:-translate-y-0.5 hover:bg-cyan-500"
            >
              Start Compound Search
            </button>
            <Link
              to="/geneExpressions"
              className="rounded-xl border border-slate-300 bg-white px-5 py-2.5 text-sm font-medium text-slate-700 transition duration-200 hover:-translate-y-0.5 hover:border-cyan-300 hover:bg-cyan-50"
            >
              Disease Molecular Signature
            </Link>
          </div>
        </div>
      </section>

      <>
        <section ref={workflowSectionRef} className="mx-auto max-w-5xl scroll-mt-28 px-2 sm:px-4">
          <form className="grid gap-5" onSubmit={handleSearch}>
            <div className="rounded-xl border border-cyan-100 bg-cyan-50/60 px-4 py-3">
              <p className="text-sm font-semibold text-cyan-900">Start with a compound</p>
              <p className="mt-1 text-sm text-cyan-800/90">
                Search by compound name or SMILES, then continue into gene-level disease matching.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <label className="relative flex-1 min-w-[240px]">
                <span className="sr-only">Compound name or SMILES</span>
                <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                <input
                  value={compoundInput}
                  onChange={handleCompoundInputChange}
                  placeholder={searchBySmile ? SMILES_PLACEHOLDER : NAME_PLACEHOLDER}
                  className="w-full rounded-xl border border-slate-300 bg-white py-2.5 pl-9 pr-3 text-sm outline-none ring-cyan-400 transition focus:border-cyan-400 focus:ring"
                />
              </label>

              <div className="inline-flex items-center rounded-xl border border-slate-300 bg-white p-1 text-sm">
                <button
                  type="button"
                  onClick={() => handleSearchModeChange('name')}
                  className={`rounded-lg px-3 py-1.5 font-semibold transition ${
                    !searchBySmile ? 'bg-cyan-600 text-white shadow-sm shadow-cyan-600/30' : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  Name
                </button>
                <button
                  type="button"
                  onClick={() => handleSearchModeChange('smiles')}
                  className={`rounded-lg px-3 py-1.5 font-semibold transition ${
                    searchBySmile ? 'bg-cyan-600 text-white shadow-sm shadow-cyan-600/30' : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  SMILES
                </button>
              </div>

              <button
                type="submit"
                disabled={isSearching || isSmilesBlocked}
                className="inline-flex items-center gap-2 rounded-xl bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm shadow-cyan-600/30 transition hover:-translate-y-0.5 hover:bg-cyan-500 disabled:opacity-50"
              >
                {isSearching ? <Loader2 className="animate-spin" size={16} /> : <FlaskConical size={16} />}
                {isSearching ? 'Searching...' : 'Fetch Compound Profile'}
              </button>

              {geneSet.length > 0 ? (
                <Link
                  to={`/geneMatch?genes=${encodeURIComponent(geneSet.join(','))}&inchikey=${encodeURIComponent(currentInchiKey)}`}
                  className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium transition hover:-translate-y-0.5 hover:border-cyan-300 hover:bg-cyan-50"
                >
                  Open Gene Match ({geneSet.length})
                </Link>
              ) : null}
            </div>

            {smilesValidationMessage ? (
              <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700" role="alert">
                {smilesValidationMessage}
              </div>
            ) : null}

            {(pubchemData || drugbankData || bioactivityRows.length > 0) ? (
              <div className="flex flex-wrap gap-2 rounded-xl border border-slate-200 bg-slate-50/80 px-3 py-2 text-xs text-slate-700">
                <span className="rounded-lg bg-white px-2 py-1">PubChem: {pubchemData ? 'Loaded' : 'Pending'}</span>
                <span className="rounded-lg bg-white px-2 py-1">DrugBank: {drugbankData ? 'Loaded' : 'Pending'}</span>
                <span className="rounded-lg bg-white px-2 py-1">Bioactivity rows: {bioactivityRows.length}</span>
                <span className="rounded-lg bg-white px-2 py-1">Genes: {geneSet.length}</span>
              </div>
            ) : null}
          </form>

          {errorMessage ? (
            <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {errorMessage}
            </div>
          ) : null}
        </section>

        <section className="mx-auto max-w-5xl px-2 sm:px-4">
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
              <SourceBadges sourceKeys={['pubchem']} className="mb-3" />
              {!pubchemData ? (
                <p className="rounded-xl border border-dashed border-slate-300 p-6 text-sm text-slate-500">No compound loaded yet.</p>
              ) : (
                <dl className="grid gap-3">
                  {chemicalIdentityEntries.map(([key, value]) => (
                    <div key={key} className="rounded-xl border border-slate-200 bg-slate-50/80 p-3.5">
                      <dt className="text-xs uppercase tracking-wide text-slate-500">{formatIdentityLabel(key)}</dt>
                      <dd className="mt-1 break-words text-sm font-medium text-slate-900">{formatValue(value)}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </TabPanel>

            <TabPanel>
              <SourceBadges sourceKeys={['drugbank']} className="mb-3" />
              {!drugbankData ? (
                <p className="rounded-xl border border-dashed border-slate-300 p-6 text-sm text-slate-500">No curated pharmacology returned for this compound.</p>
              ) : (
                <dl className="grid gap-4">
                  <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4">
                    <dt className="text-xs uppercase tracking-wide text-slate-500">DrugBank ID</dt>
                    <dd className="mt-2 break-words text-sm">{formatValue(drugbankData.drugbank_id)}</dd>
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4">
                    <dt className="text-xs uppercase tracking-wide text-slate-500">Groups</dt>
                    <dd className="mt-2 text-sm">{(drugbankData.groups ?? []).join(', ') || '--'}</dd>
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4">
                    <dt className="text-xs uppercase tracking-wide text-slate-500">Indications</dt>
                    <dd className="mt-2 text-sm">{formatValue(drugbankData.indication)}</dd>
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4">
                    <dt className="text-xs uppercase tracking-wide text-slate-500">Categories</dt>
                    <dd className="mt-2 text-sm">{(drugbankData.categories ?? []).join(', ') || '--'}</dd>
                  </div>
                </dl>
              )}
            </TabPanel>

            <TabPanel>
              <SourceBadges sourceKeys={['chembl', 'uniprot']} className="mb-3" />
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
                <label className="min-w-[280px] flex-1">
                  <span className="sr-only">Filter bioactivity rows</span>
                  <input
                    value={bioFilter}
                    onChange={(event: ChangeEvent<HTMLInputElement>) => setBioFilter(event.target.value)}
                    placeholder="Filter by target, gene, UniProt, ChEMBL ID"
                    className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm outline-none ring-cyan-400 transition focus:border-cyan-400 focus:ring"
                  />
                </label>
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
        </section>
      </>
    </AppLayout>
  );
}
