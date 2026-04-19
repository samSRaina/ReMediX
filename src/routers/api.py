from fastapi import APIRouter

from . import api_handlers as handlers

router = APIRouter(prefix="/api")


# PubChem database endpoints
router.add_api_route("/compound/name/{name}/properties", handlers.get_properties_by_name_api, methods=["GET"])
router.add_api_route("/compound/smile/{smile}/properties", handlers.get_properties_by_smile_api, methods=["GET"])

# DrugBank database endpoints
router.add_api_route("/drugbank/inchikey/{inchikey}/properties", handlers.get_properties_by_inchikey, methods=["GET"])

# ChEMBL database endpoints
router.add_api_route("/chembl/inchikey/{inchikey}/bioactivity", handlers.get_bioactivity_by_inchikey, methods=["GET"])
router.add_api_route(
    "/chembl/inchikey/{inchkey}/bioactivity/{target_chembl_id}/target",
    handlers.get_target_data,
    methods=["GET"],
)

# CREEDS endpoints
router.add_api_route("/match", handlers.get_gene_match, methods=["GET"])
router.add_api_route("/finalGeneScore", handlers.get_final_gene_score, methods=["GET"])
router.add_api_route("/geneAnalysis/accession/{accession_id}", handlers.get_gene_analysis, methods=["GET"])
router.add_api_route("/diseaseSignature/table", handlers.get_disease_signature_table, methods=["GET"])
router.add_api_route("/diseases", handlers.get_available_diseases, methods=["GET"])

# Data exploration endpoints
router.add_api_route("/geneExpressions", handlers.get_gene_expressions, methods=["GET"])
router.add_api_route("/excelData/meta", handlers.get_excel_meta, methods=["GET"])
router.add_api_route("/excelData/sheet", handlers.get_excel_sheet, methods=["GET"])
