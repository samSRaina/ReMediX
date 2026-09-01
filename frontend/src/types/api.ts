export interface DiseasesResponse {
  diseases: string[];
}

export interface PubChemCompound {
  CID?: number;
  CanonicalSMILES?: string;
  SMILES?: string;
  InChI?: string;
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
  standard_relation?: string;
  assay_chembl_id?: string;
  assay_type?: string;
  assay_description?: string;
  protein_target_classification: string;
}

export interface BioactivityResponse {
  activities: BioactivityRecord[];
  gene_set: string[];
  aggregated_targets?: AggregatedTargetRecord[];
}

export interface GeneMatchItem {
  gene: string;
  up_count?: number;
  down_count?: number;
  total_up?: number;
  total_down?: number;
  ratio: number | null;
  direction?: 'UP' | 'DOWN' | 'AMBIGUOUS' | 'up' | 'down' | 'ambiguous' | null;
  classification?: string;
  effect?: string;
  error?: string | null;
}

export interface GeneMatchResponse {
  disease: string;
  genes_matched: number;
  results: GeneMatchItem[];
}

export interface FinalGeneScoreResponse {
  score: number;
  total_sum?: number;
  offset_divisor?: number;
  genes_counted?: string[];
}

export interface AggregatedTargetMeasurement {
  activity_type?: string;
  activity_value?: string | number;
  activity_units?: string;
  relation?: string;
  assay_chembl_id?: string;
  assay_type?: string;
  assay_description?: string;
  activity_value_nm?: number;
  target_chembl_id?: string;
}

export interface AggregatedTargetRecord {
  gene_symbol: string;
  uniprot_ids: string[];
  target_chembl_ids: string[];
  target_names: string[];
  target_types: string[];
  target_organisms: string[];
  protein_target_classifications: string[];
  measurements: AggregatedTargetMeasurement[];
  activity_summary: Record<string, { count: number; representative_value_nm: number | null; units: string[] }>;
  measurement_count: number;
}

export interface RemedixGeneRecord {
  gene: string;
  U: number;
  D: number;
  disease_direction: 'UP' | 'DOWN' | 'AMBIGUOUS';
  dc: number;
  drug_action: 'INHIBITION' | 'ACTIVATION' | 'UNKNOWN';
  activity_type: string[];
  activity_strength: number;
  classification: 'BENEFICIAL' | 'HARMFUL' | 'UNRESOLVED';
  gene_contribution: number;
  activity_value_nm: number | null;
  supporting_measurements: number;
  target_chembl_ids: string[];
  uniprot_ids: string[];
}

export interface RemedixScoringSummary {
  disease: string;
  disease_total: number;
  disease_gene_set: string[];
  target_gene_total: number;
  matched_target_count: number;
  beneficial_signal: number;
  harmful_signal: number;
  net_therapeutic_signal: number;
  benefit_coverage: number;
  benefit_coverage_percent: number;
  harm_coverage: number;
  harm_coverage_percent: number;
  net_coverage: number;
  net_coverage_percent: number;
  target_coverage: number;
  target_coverage_percent: number;
  raw_remedix_score: number;
  remedix_score: number;
  directional_evidence: {
    model: string;
    source_entry_count: number;
    matched_genes: number;
  };
  gene_records: RemedixGeneRecord[];
}

export interface RemedixScoreResponse {
  inchikey: string;
  disease: string;
  aggregated_targets: AggregatedTargetRecord[];
  raw_activities: BioactivityRecord[];
  scoring: RemedixScoringSummary;
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

export interface ImageAsset {
  label: string;
  url: string;
  filename: string;
}

export interface GeneExpressionImagesResponse {
  images: ImageAsset[];
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
