import { AppLayout, Surface } from '../components/Layout';

const STEPS = [
  {
    title: '1. Compound and target discovery',
    description: 'Resolve user input into canonical chemistry metadata and collect known target evidence.',
  },
  {
    title: '2. CREEDS ambiguity filtering',
    description: 'Compute UP/DOWN dominance ratio per target and skip genes with ratio < 1.2.',
  },
  {
    title: '3. Direction + effect classification',
    description: 'Use disease signature direction (priority) with ChEMBL effect type (IC50/KI inhibitor, AC50/EC50 activator).',
  },
  {
    title: '4. Final therapeutic score',
    description: 'Sum beneficial signature scores, normalize by cached disease denominator, apply promiscuity penalty, scale by ×10, and cap at 1.0.',
  },
];

export function MethodologyPage() {
  return (
    <AppLayout>
      <section className="mx-auto max-w-5xl space-y-6">
        <Surface>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-700">Methodology</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">How RepurposeIQ computes directional therapeutic effect</h1>
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
