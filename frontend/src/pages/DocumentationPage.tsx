import { AppLayout, Surface } from '../components/Layout';

const docs = [
  {
    title: 'API Endpoints',
    items: ['/api/compound/name', '/api/compound/smile', '/api/chembl/bioactivity', '/api/match', '/api/finalGeneScore'],
  },
  {
    title: 'Data Sources',
    items: ['PubChem', 'ChEMBL', 'DrugBank', 'CREEDS', 'Local scoring sheet: src/data/data_set.xlsx'],
  },
  {
    title: 'Debug Utilities',
    items: ['gc/debug_creeds.py', 'gc/debug_final_score.py', 'gc/verify_bosentan.py', 'gc/verify_cetirizine.py'],
  },
];

export function DocumentationPage() {
  return (
    <AppLayout>
      <section className="mx-auto max-w-5xl space-y-6">
        <Surface>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-700">Documentation</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">Integration and usage references</h1>
          <p className="mt-4 max-w-3xl text-sm leading-relaxed text-slate-600 sm:text-base">
            This page keeps implementation details close to the product flow so users and developers can verify data handoff points quickly.
          </p>
        </Surface>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {docs.map((section) => (
            <Surface key={section.title}>
              <h2 className="text-lg font-semibold text-slate-900">{section.title}</h2>
              <ul className="mt-3 space-y-1.5 text-sm text-slate-600">
                {section.items.map((item) => (
                  <li key={item} className="rounded-lg bg-slate-50 px-2.5 py-2">
                    {item}
                  </li>
                ))}
              </ul>
            </Surface>
          ))}
        </div>
      </section>
    </AppLayout>
  );
}

