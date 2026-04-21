import type {
  BioactivityResponse,
  DiseaseSignatureTableResponse,
  ExcelMetaResponse,
  ExcelSheetResponse,
  DiseasesResponse,
  DrugBankData,
  FinalGeneScoreResponse,
  GeneExpressionsResponse,
  GeneMatchResponse,
  PubChemCompound,
} from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

interface FastApiValidationDetailItem {
  loc?: unknown;
  msg?: unknown;
}

function formatApiDetail(detail: unknown): string | null {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (!item || typeof item !== 'object') return null;
        const entry = item as FastApiValidationDetailItem;
        const loc = Array.isArray(entry.loc) ? entry.loc.join('.') : '';
        const msg = typeof entry.msg === 'string' ? entry.msg : '';
        if (!loc && !msg) return null;
        return loc ? `${loc}: ${msg}` : msg;
      })
      .filter(Boolean) as string[];
    if (parts.length > 0) return parts.join(' | ');
  }
  if (detail && typeof detail === 'object') return JSON.stringify(detail);
  return null;
}

async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      const parsed = formatApiDetail(body?.detail);
      if (parsed) detail = parsed;
    } catch {
      // Keep fallback detail when response body is not JSON.
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export function getDiseases() {
  return apiGet<DiseasesResponse>('/api/diseases');
}

export function getCompoundByName(name: string) {
  return apiGet<PubChemCompound>(`/api/compound/name/${encodeURIComponent(name)}/properties`);
}

export function getCompoundBySmile(smile: string) {
  return apiGet<PubChemCompound>(`/api/compound/smile/${encodeURIComponent(smile)}/properties`);
}

export function getDrugBankByInchiKey(inchiKey: string) {
  return apiGet<DrugBankData>(`/api/drugbank/inchikey/${encodeURIComponent(inchiKey)}/properties`);
}

export function getBioactivityByInchiKey(inchiKey: string, standardType: string) {
  const query = new URLSearchParams({ standard_type: standardType });
  return apiGet<BioactivityResponse>(`/api/chembl/inchikey/${encodeURIComponent(inchiKey)}/bioactivity?${query.toString()}`);
}

export function getGeneMatch(genes: string, disease: string) {
  const query = new URLSearchParams({ genes, disease });
  return apiGet<GeneMatchResponse>(`/api/match?${query.toString()}`);
}

export interface FinalGeneScoreParams {
  inchikey: string;
  disease: string;
}

export function getFinalGeneScore(params: FinalGeneScoreParams) {
  const query = new URLSearchParams({ inchikey: params.inchikey, disease: params.disease });
  return apiGet<FinalGeneScoreResponse>(`/api/finalGeneScore?${query.toString()}`);
}

export function getDiseaseSignatureTable(disease: string, page = 1, pageSize = 100) {
  const query = new URLSearchParams({ disease, page: String(page), page_size: String(pageSize) });
  return apiGet<DiseaseSignatureTableResponse>(`/api/diseaseSignature/table?${query.toString()}`);
}

export function getGeneExpressions(page = 1, pageSize = 50, search?: string) {
  const query = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (search) query.set('search', search);
  return apiGet<GeneExpressionsResponse>(`/api/geneExpressions?${query.toString()}`);
}

export function getExcelMeta() {
  return apiGet<ExcelMetaResponse>('/api/excelData/meta');
}

export function getExcelSheetPage(name: string, page = 1, pageSize = 100) {
  const query = new URLSearchParams({ name, page: String(page), page_size: String(pageSize) });
  return apiGet<ExcelSheetResponse>(`/api/excelData/sheet?${query.toString()}`);
}
