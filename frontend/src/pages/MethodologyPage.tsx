import { AppLayout, Surface } from '../components/Layout';
import { SourceBadges } from '../components/SourceBadges';

const STEPS = [
  {
    title: '1) Drug Identification and Canonical Chemistry',
    description: 'Resolve user input with PubChem and retain canonical identity fields (CID, Canonical SMILES, InChI/InChIKey, formula, molecular weight, and supporting physicochemical properties).',
  },
  {
    title: '2–4) Drug Info and Target Profiling',
    description: 'Keep DrugBank annotation and ChEMBL target evidence, then normalize targets with UniProt identifiers for consistent downstream gene-level scoring.',
  },
  {
    title: '5–7) Direction Consensus and Overlap',
    description: 'For each disease gene, compute U/D observation counts from CREEDS and Direction Consensus DC=|U-D|/(U+D). Intersect drug targets with the unique CREEDS disease gene set before scoring.',
  },
  {
    title: '8–9) Pharmacology-aware Contribution',
    description: 'Use ChEMBL activity values to compute bounded activity strength and combine it with DC using GeneContribution = DC × (0.7 + 0.3 × ActivityStrength).',
  },
  {
    title: '10–12) Beneficial vs Harmful Signal',
    description: 'Classify each matched gene as BENEFICIAL/HARMFUL/UNRESOLVED from disease direction and drug action mapping (IC50/Ki inhibitory, AC50 activating), then compute B, H, and NetSignal = B-H.',
  },
  {
    title: '13–19) Disease-normalized Scoring',
    description: 'Normalize by disease gene space (DiseaseTotal) to produce BenefitCoverage, HarmCoverage, NetCoverage, TargetCoverage, signed RawReMediXScore, and clipped public ReMediX Score (0–100).',
  },
  {
    title: '20–21) Traceable Output',
    description: 'Return both summary metrics and per-gene traceability (U, D, direction, DC, drug action, activity strength, classification, contribution) for transparent evidence tracking.',
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
              <SourceBadges matchText={`${step.title} ${step.description}`} className="mt-3" />
            </Surface>
          ))}
        </div>
      </section>
    </AppLayout>
  );
}
