import { AppLayout, Surface } from '../components/Layout';

const docs = [
  {
    title: 'Data Sources',
    items: ['PubChem', 'DrugBank', 'ChEMBL','UniProt', 'CREEDS', 'GeneCards', 'GEO', 'Reactome', 'OpenTargets' ],
  },
];

export function DocumentationPage() {
  return (
    <AppLayout>
      <section className="mx-auto max-w-5xl space-y-6">
        <Surface>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-700">Documentation</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">Usage references</h1>
          <p className="mt-4 max-w-3xl text-sm leading-relaxed text-slate-600 sm:text-base">
            This page keeps implementation details close to the product flow so users can verify data handoff points quickly.
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

