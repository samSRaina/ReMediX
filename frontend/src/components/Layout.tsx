import { NavLink } from 'react-router-dom';
import type { ReactNode } from 'react';

const navItems = [
  { to: '/', label: 'Home' },
  { to: '/about', label: 'About' },
  { to: '/methodology', label: 'Methodology' },
  { to: '/documentation', label: 'Documentation' },
  { to: '/scoringResults', label: 'Scoring Results' },
];

export function AppLayout({ children, fullWidth = false }: { title?: string; subtitle?: string; children: ReactNode; fullWidth?: boolean }) {
  return (
    <div className="min-h-screen px-4 pb-6 pt-2 text-slate-900 sm:pb-8 sm:pt-3">
      <div className={`${fullWidth ? 'w-full' : 'mx-auto max-w-7xl'} space-y-6`}>
        <header className="sticky top-0 z-40 py-1.5 sm:py-2">
          <nav className="mx-auto flex w-full max-w-6xl items-center justify-between rounded-2xl border border-white/70 bg-white/75 px-2 py-2 shadow-[0_10px_35px_-22px_rgba(15,23,42,0.55)] backdrop-blur-xl">
            <span className="px-3 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">ReMediX</span>
            <div className="flex flex-wrap items-center gap-1.5 rounded-xl border border-slate-200/80 bg-white/80 p-1">
              {navItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `rounded-lg px-4 py-2 text-sm font-medium transition duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-1 ${
                      isActive
                        ? 'bg-gradient-to-r from-cyan-600 to-cyan-500 text-white shadow-sm shadow-cyan-700/30'
                        : 'text-slate-700 hover:bg-slate-100 hover:text-cyan-700'
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </div>
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


