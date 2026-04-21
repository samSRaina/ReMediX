import { AppLayout, Surface } from '../components/Layout';

const STEPS = [
  {
    title: 'Input Validation & Molecular Standardization',
    description: 'Resolve user input (SMILES/compound name) into a canonical chemical structure.\n' +
        'Filter out salts, mixtures, and non-biological entities to ensure only valid parent molecules proceed.',
  },
  {
    title: 'Compound Annotation & Target Profiling\n',
    description: 'Retrieve chemical identity and pharmacological data via PubChem, DrugBank, and ChEMBL APIs.\n' +
        'Generate a drug–target gene list using IC₅₀ / Ki / AC₅₀ bioactivity data mapped to gene symbols and UniProt IDs.',
  },
  {
    title: 'Perturbation Direction Mapping \n',
    description: 'Determine whether each target gene is upregulated or downregulated in disease using CREEDS.\n' +
        'Filter out ambiguous genes and retain only directionally confident targets.',
  },
  {
    title: 'Disease Signature Integration & Network Context\n',
    description: 'Compare drug targets against a weighted disease molecular signature\n' +
        '(built from GeneCards, GEO, Reactome, Open Targets).\n' +
        'Incorporate PPI network context (STRING/Cytoscape) to identify biologically relevant overlaps',
  },
    {
    title: 'Therapeutic Relevance Scoring\n',
    description: 'Classify interactions as beneficial or harmful based on transcriptomic reversal\n' +
        'Compute a final normalized score (0–1) using weighted gene contributions and target selectivity\n' +
        'delivering an interpretable drug–disease relevance output',
  },
];

export function MethodologyPage() {
  return (
    <AppLayout>
      <section className="mx-auto max-w-5xl space-y-6">
        <Surface>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-700">Methodology</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">How ReMediX computes directional therapeutic effect</h1>
          <p className="mt-4 max-w-3xl text-sm leading-relaxed text-slate-600 sm:text-base">
            The pipeline keeps each computational step observable so you can inspect exactly where a compound gains or loses confidence.
          </p>
        </Surface>

        <div className="grid gap-4 sm:grid-cols-2">
          {STEPS.map((step) => (
            <Surface key={step.title}>
              <h2 className="text-lg font-semibold text-slate-900">{step.title}</h2>
              <p className="mt-2 text-sm leading-relaxed text-slate-600">{step.description}</p>
            </Surface>
          ))}
        </div>
      </section>
    </AppLayout>
  );
}

