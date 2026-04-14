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
    <div className="min-h-screen px-4 py-6 text-slate-900 sm:py-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <header className="panel-soft sticky top-3 z-30 p-4 sm:p-5">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-cyan-600">Drug Repurposing Platform</p>
              <h1 className="mt-1 text-2xl font-bold tracking-tight sm:text-[1.7rem]">{title}</h1>
              {subtitle ? <p className="mt-1 text-sm text-slate-500">{subtitle}</p> : null}
            </div>
            <Link
              to="/"
              className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm font-medium transition hover:-translate-y-0.5 hover:border-cyan-300 hover:bg-cyan-50"
            >
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
                    isActive
                      ? 'bg-cyan-600 text-white shadow-sm shadow-cyan-600/30'
                      : 'border border-slate-300 bg-white hover:-translate-y-0.5 hover:border-cyan-300 hover:bg-cyan-50'
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
  return <section className="panel-soft p-5 sm:p-6">{children}</section>;
}


