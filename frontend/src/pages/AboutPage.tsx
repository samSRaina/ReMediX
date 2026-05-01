import { AppLayout, Surface } from '../components/Layout';
import { SourceBadges } from '../components/SourceBadges';

export function AboutPage() {
  return (
    <AppLayout>
      <section className="mx-auto max-w-5xl space-y-6">
        <Surface>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-700">About ReMedix</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">Disease-aware drug repurposing for translational teams</h1>
          <p className="mt-4 max-w-3xl text-sm leading-relaxed text-slate-600 sm:text-base">
            ReMediX combines public chemistry, target, perturbation, and disease-signature data to highlight compounds with
            beneficial reversal potential. The workflow is designed for fast hypothesis generation while staying traceable to source datasets.
          </p>
        </Surface>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[
            {
              title: 'Evidence Layers',
              body: 'PubChem, ChEMBL, DrugBank, and CREEDS are merged into one scoring pipeline with transparent intermediate outputs.',
            },
            {
              title: 'Decision Support',
              body: 'Directional therapeutic effect and final score are shown together so researchers can inspect both confidence and impact.',
            },
            {
              title: 'Clinical Framing',
              body: 'Disease context is selected by users at runtime, avoiding hard-coded assumptions and preserving workflow flexibility.',
            },
          ].map((item) => (
            <Surface key={item.title}>
              <h2 className="text-lg font-semibold text-slate-900">{item.title}</h2>
              <p className="mt-2 text-sm leading-relaxed text-slate-600">{item.body}</p>
              <SourceBadges matchText={item.body} className="mt-3" />
            </Surface>
          ))}
        </div>
      </section>
    </AppLayout>
  );
}
