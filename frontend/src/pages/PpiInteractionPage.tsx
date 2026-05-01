import { useState } from 'react';
import { AppLayout, Surface } from '../components/Layout';
import { SourceBadges } from '../components/SourceBadges';

const excelLinks = [
  ['Protein Node Degrees', '/data/PPInteraction/xlsxData/1_Protein Node Degrees.xlsx'],
  ['Network Coordinates', '/data/PPInteraction/xlsxData/2_Network Coordinates.xlsx'],
  ['KEGG Enrichment', '/data/PPInteraction/xlsxData/4_KEGG Enrichment.xlsx'],
  ['Biological Process', '/data/PPInteraction/xlsxData/6_Gene Ontology_Biological Process.xlsx'],
  ['GO Molecular Function', '/data/PPInteraction/xlsxData/8_Gene Ontology_ Molecular function.xlsx'],
  ['GO Cellular Components', '/data/PPInteraction/xlsxData/10_Gene Ontology_Cellular Components.xlsx'],
  ['Disease Expression', '/data/PPInteraction/xlsxData/12_Disease Expression.xlsx'],
  ['Tissue Expression', '/data/PPInteraction/xlsxData/14_Tissue Expression.xlsx'],
  ['Reactome', '/data/PPInteraction/xlsxData/15_Reactome.xlsx'],
  ['Cytoscape Network Data', '/data/PPInteraction/xlsxData/16_Cytoscape_Network Data.xlsx'],
] as const;

const images = [
  ['STRING', '/data/PPInteraction/STRING.png'],
  ['KEGG Enrichment', '/data/PPInteraction/5_KEGG Enrichment.png'],
  ['Gene Ontology Biological Process', '/data/PPInteraction/7_Gene Ontology_ Biological Process.png'],
  ['Gene Ontology Molecular Function', '/data/PPInteraction/9_ Gene Ontology_ Molecular Function.png'],
  ['Gene Ontology Cellular Components', '/data/PPInteraction/11_ Gene Ontology_ Cellular Components.png'],
  ['Disease Expression', '/data/PPInteraction/13_Disease Expression.png'],
  ['Cytoscape Network', '/data/PPInteraction/17_Cytoscape_Network.png'],
] as const;

const EXCEL_SOURCE_TEXT = excelLinks.map(([label]) => label).join(' ');
const IMAGE_SOURCE_TEXT = images.map(([label]) => label).join(' ');

export function PpiInteractionPage() {
  const [preview, setPreview] = useState<{ title: string; src: string } | null>(null);

  return (
    <AppLayout title="PPI Interaction" subtitle="Network-level interaction visualizations and supporting sheets">
      <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
        <Surface>
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600">PPI Excel Sheets</h2>
            <SourceBadges matchText={EXCEL_SOURCE_TEXT} />
          </div>
          <p className="mb-3 text-xs text-slate-500">Files open in a new tab. Some browsers may download .xlsx files.</p>
          <div className="space-y-2">
            {excelLinks.map(([label, href]) => (
              <a
                key={label}
                href={href}
                target="_blank"
                rel="noreferrer"
                className="block rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm transition hover:-translate-y-0.5 hover:border-cyan-300 hover:bg-cyan-50"
              >
                {label}
              </a>
            ))}
          </div>
        </Surface>

        <Surface>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600">Images</h2>
            <SourceBadges matchText={IMAGE_SOURCE_TEXT} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {images.map(([title, src]) => (
              <button
                key={title}
                type="button"
                onClick={() => setPreview({ title, src })}
                className="overflow-hidden rounded-xl border border-slate-200 bg-white text-left transition hover:-translate-y-0.5 hover:border-cyan-300 hover:shadow-md"
              >
                <img src={src} alt={title} className="h-44 w-full object-contain bg-slate-50" />
                <div className="px-3 py-2 text-sm font-medium">{title}</div>
              </button>
            ))}
          </div>
        </Surface>
      </div>

      {preview ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={() => setPreview(null)}>
          <div className="max-h-[92vh] w-full max-w-6xl rounded-xl border border-slate-200 bg-white p-4 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-sm font-semibold">{preview.title}</h3>
              <button type="button" onClick={() => setPreview(null)} className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm transition hover:border-cyan-300 hover:bg-cyan-50">Close</button>
            </div>
            <img src={preview.src} alt={preview.title} className="max-h-[80vh] w-full object-contain" />
          </div>
        </div>
      ) : null}
    </AppLayout>
  );
}
