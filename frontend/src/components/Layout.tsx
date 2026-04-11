import { Link, NavLink } from 'react-router-dom';
import type { ReactNode } from 'react';

const navItems = [
  { to: '/', label: 'Home' },
  //{ to: '/geneMatch', label: 'Gene Match' },
  { to: '/geneExpressions', label: 'Gene Expressions' },
  { to: '/excelViewer', label: 'Data Viewer' },
  { to: '/ppiInteraction', label: 'PPI Interaction' },
];

export function AppLayout({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-cyan-50 to-slate-100 px-4 py-8 text-slate-900">
      <div className="mx-auto max-w-7xl space-y-6">
        <header className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-cyan-600">Drug Repurposing Platform</p>
              <h1 className="text-2xl font-bold">{title}</h1>
              {subtitle ? <p className="text-sm text-slate-500">{subtitle}</p> : null}
            </div>
            <Link to="/" className="rounded-xl border border-slate-300 px-3 py-2 text-sm font-medium transition hover:bg-slate-50">
              Back to Home
            </Link>
          </div>
          <nav className="mt-4 flex flex-wrap gap-2">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }: { isActive: boolean }) =>
                  `rounded-xl px-3 py-2 text-sm font-medium transition ${
                    isActive ? 'bg-cyan-600 text-white' : 'border border-slate-300 bg-white hover:bg-slate-50'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </header>

        {children}
      </div>
    </div>
  );
}

export function Surface({ children }: { children: ReactNode }) {
  return <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">{children}</section>;
}


