import { useId, useMemo } from 'react';
import type { SourceReference } from '../lib/sources';
import { useSources } from '../lib/sources';

const EXTRA_ALIASES: Record<string, string[]> = {
  opentargets: ['open targets'],
  genecards: ['gene cards'],
};

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function getAliases(key: string): string[] {
  const normalized = key.toLowerCase();
  const parts = normalized.split(':').flatMap((part) => part.split(/[_-]/g));
  const aliases = new Set<string>([normalized, ...parts]);
  (EXTRA_ALIASES[normalized] ?? []).forEach((alias) => aliases.add(alias));
  return Array.from(aliases).filter(Boolean);
}

function matchesAlias(text: string, alias: string): boolean {
  const normalizedText = text.toLowerCase();
  if (alias.includes(' ')) {
    return normalizedText.includes(alias);
  }
  const pattern = new RegExp(`\\b${escapeRegExp(alias)}\\b`, 'i');
  return pattern.test(normalizedText);
}

function resolveSources(
  sources: SourceReference[],
  sourceKeys?: string[],
  matchText?: string,
): SourceReference[] {
  const resolved: SourceReference[] = [];
  const seen = new Set<string>();
  const byKey = new Map(sources.map((source) => [source.key.toLowerCase(), source]));

  sourceKeys?.forEach((key) => {
    const match = byKey.get(key.toLowerCase());
    if (match && !seen.has(match.key)) {
      seen.add(match.key);
      resolved.push(match);
    }
  });

  if (matchText) {
    const normalized = matchText.toLowerCase();
    sources.forEach((source) => {
      if (seen.has(source.key)) return;
      const aliases = getAliases(source.key);
      if (aliases.some((alias) => matchesAlias(normalized, alias))) {
        seen.add(source.key);
        resolved.push(source);
      }
    });
  }

  return resolved;
}

function buildJournalLine(source: SourceReference): string | null {
  const parts: string[] = [];
  if (source.journal) parts.push(source.journal);
  if (source.year) parts.push(String(source.year));
  const volumeIssue = [source.volume, source.issue ? `(${source.issue})` : null].filter(Boolean).join('');
  if (volumeIssue) parts.push(volumeIssue);
  if (source.pages) parts.push(source.pages);
  return parts.length > 0 ? parts.join(' • ') : null;
}

function formatYear(year: number | null): string {
  return year ? String(year) : 'Year N/A';
}

export function SourceBadges({
  sourceKeys,
  matchText,
  fallbackLabel,
  className = '',
}: {
  sourceKeys?: string[];
  matchText?: string;
  fallbackLabel?: string;
  className?: string;
}) {
  const { sources } = useSources();
  const instanceId = useId();
  const resolvedSources = useMemo(
    () => resolveSources(sources, sourceKeys, matchText),
    [sources, sourceKeys, matchText],
  );

  if (resolvedSources.length === 0) {
    return fallbackLabel ? (
      <span className="text-xs text-slate-600">{fallbackLabel}</span>
    ) : null;
  }

  return (
    <div className={`flex flex-wrap items-start gap-2 ${className}`}>
      {resolvedSources.map((source) => {
        const journalLine = buildJournalLine(source);
        const tooltipId = `source-tooltip-${instanceId}-${source.key.replace(/[^a-z0-9]+/gi, '-')}`;
        return (
          <div key={source.key} className="group relative inline-flex max-w-[240px]">
            <div
              tabIndex={0}
              aria-describedby={tooltipId}
              onKeyDown={(event) => {
                if (event.key === 'Escape') {
                  (event.currentTarget as HTMLDivElement).blur();
                }
              }}
              className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700 shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-1"
            >
              <div className="leading-snug text-slate-700">{source.title}</div>
              <div className="text-[10px] font-medium text-slate-500">{formatYear(source.year)}</div>
            </div>
            <div
              id={tooltipId}
              role="tooltip"
              className="pointer-events-none invisible absolute left-1/2 top-full z-30 mt-2 w-72 max-w-[75vw] -translate-x-1/2 translate-y-1 opacity-0 transition group-hover:visible group-hover:pointer-events-auto group-hover:opacity-100 group-focus-within:visible group-focus-within:pointer-events-auto group-focus-within:opacity-100"
            >
              <div className="rounded-xl border border-slate-200 bg-white p-3 text-xs text-slate-600 shadow-xl">
                <p className="text-sm font-semibold text-slate-900">
                  {source.title} {source.year ? `(${source.year})` : ''}
                </p>
                <p className="mt-1">{source.authors}</p>
                {journalLine ? <p className="mt-1 italic text-slate-700">{journalLine}</p> : null}
                {source.doi ? <p className="mt-1">DOI: {source.doi}</p> : null}
                {source.url ? <p className="mt-1 break-words">{source.url}</p> : null}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
