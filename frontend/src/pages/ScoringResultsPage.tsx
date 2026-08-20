import { Link } from 'react-router-dom';
import { AppLayout, Surface } from '../components/Layout';

export function ScoringResultsPage() {
  return (
    <AppLayout>
      <section className="mx-auto max-w-5xl space-y-6">
        <Surface>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-700">Scoring Results</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">Read final disease therapeutic effect</h1>
          <p className="mt-4 max-w-3xl text-sm leading-relaxed text-slate-600 sm:text-base">
            ReMediX now retains both a signed internal score and a clipped public score, along with beneficial/harmful/net signals and disease-normalized coverage metrics.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link
              to="/"
              className="rounded-xl bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm shadow-cyan-600/30 transition hover:-translate-y-0.5 hover:bg-cyan-500"
            >
              Run New Compound
            </Link>
            {/*<Link
              to="/geneMatch"
              className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:-translate-y-0.5 hover:border-cyan-300 hover:bg-cyan-50"
            >
              Open Match Workspace
            </Link>*/}
          </div>
        </Surface>

        <div className="grid gap-4 sm:grid-cols-3">
          <Surface>
            <p className="text-sm font-semibold text-slate-900">Raw Score &gt; 0</p>
            <p className="mt-2 text-sm text-slate-600">Predominantly beneficial alignment after subtracting harmful directional burden.</p>
          </Surface>
          <Surface>
            <p className="text-sm font-semibold text-slate-900">Raw Score ≈ 0</p>
            <p className="mt-2 text-sm text-slate-600">Weak or mixed alignment where beneficial and harmful evidence nearly cancel.</p>
          </Surface>
          <Surface>
            <p className="text-sm font-semibold text-slate-900">Raw Score &lt; 0</p>
            <p className="mt-2 text-sm text-slate-600">Predominantly harmful directional alignment; internal signed value is preserved for traceability.</p>
          </Surface>
        </div>
      </section>
    </AppLayout>
  );
}
