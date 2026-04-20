export interface DiseasesResponse {
  diseases: string[];
}

export interface PubChemCompound {
  CID?: number;
  SMILES?: string;
  IUPACName?: string;
  MolecularFormula?: string;
  MolecularWeight?: number;
  InChIKey?: string;
  XLogP?: number;
  TPSA?: number;
  HBondDonorCount?: number;
  HBondAcceptorCount?: number;
  RotatableBondCount?: number;
}

export interface DrugBankData {
  drugbank_id?: string;
  name?: string;
  groups?: string[];
  indication?: string;
  categories?: string[];
  targets?: string[];
  inchi_key?: string;
}

export interface BioactivityRecord {
  target_chembl_id: string;
  target_name: string;
  target_type: string;
  target_organism: string;
  gene_symbol: string;
  uniprot_id: string;
  standard_type: string;
  standard_value: string;
  standard_units: string;
  protein_target_classification: string;
}

export interface BioactivityResponse {
  activities: BioactivityRecord[];
  gene_set: string[];
}

export interface GeneMatchItem {
  gene: string;
  up_count: number;
  down_count: number;
  ratio: number | null;
  direction: 'UP' | 'DOWN' | 'AMBIGUOUS' | null;
  classification: string;
  effect: string;
  disease_direction?: string | null;
  disease_score?: number | null;
  skip_reason?: string | null;
}

export interface GeneMatchResponse {
  disease: string;
  genes_matched: number;
  results: GeneMatchItem[];
}

export interface FinalGeneScoreResponse {
  drug: string;
  disease: string;
  numerator: number;
  denominator: number;
  raw_score: number;
  promiscuity_penalty: number;
  target_count: number;
  final_score: number;
  category: 'High' | 'Moderate' | 'Low';
  beneficial_genes: Array<{ gene: string; contribution: number }>;
  gene_breakdown: Array<{
    gene: string;
    standard_type: string;
    drug_effect: string;
    up_count: number;
    down_count: number;
    creeds_ratio: number | null;
    creeds_direction: string | null;
    disease_direction_source: string | null;
    disease_direction: string | null;
    disease_signature_score: number | null;
    weight: number;
    classification: string;
    contribution: number;
    skip_reason: string | null;
  }>;
}

export interface DiseaseSignatureTableResponse {
  disease: string;
  headers: string[];
  data: Array<Array<string | number>>;
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}

export interface GeneExpressionsResponse {
  data: Array<Record<string, string | number | null>>;
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface ExcelMetaResponse {
  sheetNames: string[];
  meta: Record<string, { headers: string[]; totalRows: number }>;
}

export interface ExcelSheetResponse {
  headers: Array<string | null>;
  data: Array<Array<string | number | null>>;
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}
