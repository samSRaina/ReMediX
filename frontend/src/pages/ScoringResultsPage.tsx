import { Link } from 'react-router-dom';
import { AppLayout, Surface } from '../components/Layout';

export function ScoringResultsPage() {
  return (
    <AppLayout>
      <section className="mx-auto max-w-5xl space-y-6">
        <Surface>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-700">Scoring Results</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">Read final disease therapeutic effect in context</h1>
          <p className="mt-4 max-w-3xl text-sm leading-relaxed text-slate-600 sm:text-base">
            Final score ranges from 0 to 1 and is computed as (numerator / denominator) × promiscuity penalty × 10 with a hard cap at 1.0.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link
              to="/"
              className="rounded-xl bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm shadow-cyan-600/30 transition hover:-translate-y-0.5 hover:bg-cyan-500"
            >
              Run New Compound
            </Link>
            <Link
              to="/geneMatch"
              className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:-translate-y-0.5 hover:border-cyan-300 hover:bg-cyan-50"
            >
              Open Match Workspace
            </Link>
          </div>
        </Surface>

        <div className="grid gap-4 sm:grid-cols-3">
          <Surface>
            <p className="text-sm font-semibold text-slate-900">&gt; 0.05</p>
            <p className="mt-2 text-sm text-slate-600">High repurposing potential (Green).</p>
          </Surface>
          <Surface>
            <p className="text-sm font-semibold text-slate-900">0.02 - 0.05</p>
            <p className="mt-2 text-sm text-slate-600">Moderate repurposing potential (Amber).</p>
          </Surface>
          <Surface>
            <p className="text-sm font-semibold text-slate-900">&lt; 0.02</p>
            <p className="mt-2 text-sm text-slate-600">Low repurposing potential (Red).</p>
          </Surface>
        </div>
      </section>
    </AppLayout>
  );
}
