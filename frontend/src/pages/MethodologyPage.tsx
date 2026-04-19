import { AppLayout, Surface } from '../components/Layout';

const STEPS = [
  {
    title: '1. Compound and target discovery',
    description: 'Resolve user input into canonical chemistry metadata and collect known target evidence.',
  },
  {
    title: '2. Perturbation-direction filtering',
    description: 'Estimate UP/DOWN tendency per target from single gene perturbations and remove ambiguous targets.',
  },
  {
    title: '3. Disease overlap matching',
    description: 'Compare directional target effects against disease signature direction to classify beneficial vs harmful overlap.',
  },
  {
    title: '4. Therapeutic effect scoring',
    description: 'Aggregate matched disease-signature values into a normalized final score between 0 and 1.',
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

