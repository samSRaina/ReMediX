// Field mappings for cleaner code
const PUBCHEM_FIELDS = {
    'compound': { key: null, isInput: true },
    'smile': { key: 'SMILES' },
    'pubchem-id': { key: 'CID' },
    'iupac': { key: 'IUPACName' },
    'molecular-formula': { key: 'MolecularFormula' },
    'molecular-weight': { key: 'MolecularWeight' },
    'inchi-key': { key: 'InChIKey' },
    'hbd': { key: 'HBondDonorCount' },
    'hba': { key: 'HBondAcceptorCount' },
    'xlogp': { key: 'XLogP' },
    'tpsa': { key: 'TPSA' },
    'rotatable-bonds': { key: 'RotatableBondCount' }
};

const DRUGBANK_FIELDS = {
    'drug-group': { key: 'groups', isArray: true },
    'indications': { key: 'indication' },
    'targets': { key: 'targets', isArray: true },
    'category': { key: 'categories', isArray: true }
};

// Store current InChIKey for bioactivity fetching
let currentInChIKey = null;
let currentBioactivityType = 'IC50';
let currentGeneSet = [];
let requestController = null;

// Bioactivity table columns
const BIOACTIVITY_COLUMNS = [
    'target_chembl_id',
    'target_name',
    'target_type',
    'target_organism',
    'gene_symbol',
    'uniprot_id',
    'standard_type',
    'standard_value',
    'standard_units',
    'protein_target_classification'
];

// Fetch and display bioactivity data
async function fetchBioactivity(inchiKey, standardType, signal) {
    const tbody = document.getElementById('bioactivity-tbody');
    const emptyState = document.getElementById('bioactivity-empty');

    // Clear existing data
    tbody.innerHTML = '';
    emptyState.style.display = 'none';

    if (!inchiKey) {
        emptyState.style.display = 'block';
        return;
    }

    try {
        const url = `/api/chembl/inchikey/${inchiKey}/bioactivity?standard_type=${standardType}`;
        const response = await fetch(url, { signal });

        if (!response.ok) {
            emptyState.style.display = 'block';
            return;
        }

        const json = await response.json();
        const activities = json.activities || [];
        currentGeneSet = json.gene_set || [];

        if (activities.length === 0) {
            emptyState.style.display = 'block';
            return;
        }

        // Populate table rows
        activities.forEach(row => {
            const tr = document.createElement('tr');
            BIOACTIVITY_COLUMNS.forEach(col => {
                const td = document.createElement('td');
                const val = row[col];
                td.textContent = (val !== null && val !== undefined && val !== '') ? val : '--';
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });

        // Show/update gene match link
        updateGeneMatchLink();

    } catch (err) {
        if (err.name === 'AbortError') {
            return;
        }
        console.error('Bioactivity fetch error:', err);
        emptyState.style.display = 'block';
    }
}

// Show or hide the gene match navigation link
function updateGeneMatchLink() {
    let link = document.getElementById('gene-match-link');
    if (currentGeneSet.length > 0) {
        if (!link) {
            link = document.createElement('a');
            link.id = 'gene-match-link';
            link.className = 'btn btn-outline-dark btn-sm mt-2';
            document.getElementById('chembl').querySelector('.card-body').appendChild(link);
        }
        link.href = `/geneMatch?genes=${encodeURIComponent(currentGeneSet.join(','))}`;
        link.textContent = `Match ${currentGeneSet.length} gene(s) on next page →`;
        link.style.display = 'inline-block';
    } else if (link) {
        link.style.display = 'none';
    }
}

// Handle tab click
function handleTabClick(e) {
    const tab = e.target;
    if (!tab.classList.contains('bioactivity-tab')) return;

    // Update active state
    document.querySelectorAll('.bioactivity-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');

    // Get selected type and fetch data
    currentBioactivityType = tab.dataset.type;
    if (currentInChIKey) {
        fetchProperties({ skipCoreFetch: true });
    }
}

// Clear bioactivity table
function clearBioactivity() {
    document.getElementById('bioactivity-tbody').innerHTML = '';
    document.getElementById('bioactivity-empty').style.display = 'block';
    currentInChIKey = null;
    currentGeneSet = [];
    const link = document.getElementById('gene-match-link');
    if (link) link.style.display = 'none';
}

// Clear all result fields
function clearResults() {
    // Clear PubChem fields
    Object.keys(PUBCHEM_FIELDS).forEach(id => {
        document.getElementById(id).innerText = '';
    });
    document.getElementById('compound-result').style.display = 'none';

    // Clear DrugBank fields
    Object.keys(DRUGBANK_FIELDS).forEach(id => {
        document.getElementById(id).innerText = '';
    });

    // Clear bioactivity table
    clearBioactivity();
}

// Display PubChem data
function displayPubchemData(data, input) {
    document.getElementById('compound').innerText = input;
    document.getElementById('compound-result').style.display = 'block';

    Object.entries(PUBCHEM_FIELDS).forEach(([id, config]) => {
        if (config.isInput) return;
        document.getElementById(id).innerText = data[config.key] || '';
    });
}

// Display DrugBank data
function displayDrugbankData(data) {
    Object.entries(DRUGBANK_FIELDS).forEach(([id, config]) => {
        const value = data[config.key];
        document.getElementById(id).innerText = config.isArray
            ? (value || []).join(', ')
            : (value || '');
    });
}

// Clear DrugBank fields
function clearDrugbankData() {
    Object.keys(DRUGBANK_FIELDS).forEach(id => {
        document.getElementById(id).innerText = '';
    });
}

// Show error message
function showError(message) {
    clearResults();
    document.getElementById('error-message').innerText = message;
}

// Fetch properties from API
async function fetchProperties(options = {}) {
    const request = requestController.begin();
    const signal = request.signal;
    const input = document.getElementById('compound-input').value.trim();
    if (!input && !options.skipCoreFetch) {
        showError('Please enter a compound name or SMILE');
        requestController.end(request);
        return;
    }

    const isSmileSearch = document.getElementById('searchbar-toggle').checked;
    const endpoint = isSmileSearch
        ? `/api/compound/smile/${encodeURIComponent(input)}/properties`
        : `/api/compound/name/${encodeURIComponent(input)}/properties`;

    try {
        // First fetch PubChem to get InChIKey
        let pubchemData = null;
        if (!options.skipCoreFetch) {
            const responsePubchem = await fetch(endpoint, { signal });
            if (!responsePubchem.ok) {
                throw new Error('Compound not found or API error');
            }
            pubchemData = await responsePubchem.json();
        } else {
            pubchemData = { InChIKey: currentInChIKey };
        }

        // Fetch DrugBank in parallel if InChIKey exists
        let drugbankData = null;
        if (pubchemData?.InChIKey && !options.skipCoreFetch) {
            const responseDrugbank = await fetch(`/api/drugbank/inchikey/${pubchemData.InChIKey}/properties`, { signal });
            if (responseDrugbank.ok) {
                drugbankData = await responseDrugbank.json();
            }
        }

        // Display both datasets together
        if (!options.skipCoreFetch) {
            displayPubchemData(pubchemData, input);
            if (drugbankData) {
                displayDrugbankData(drugbankData);
            } else {
                clearDrugbankData();
            }
        }

        // Fetch bioactivity data if InChIKey exists
        if (pubchemData?.InChIKey) {
            currentInChIKey = pubchemData.InChIKey;
            await fetchBioactivity(currentInChIKey, currentBioactivityType, signal);
        } else {
            clearBioactivity();
        }

    } catch (err) {
        if (err.name === 'AbortError') {
            document.getElementById('error-message').innerText = 'Request cancelled.';
            return;
        }
        showError(err.message || 'An error occurred.');
    } finally {
        requestController.end(request);
    }
}

// Initialize event listeners when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const getPropertiesBtn = document.getElementById('get-properties-btn');
    const stopBtn = document.getElementById('stop-home-btn');
    requestController = createRequestController({
        runButtons: [getPropertiesBtn],
        cancelButton: stopBtn
    });

    document.getElementById('home-form').addEventListener('submit', (e) => {
        e.preventDefault();
        document.getElementById('error-message').innerText = '';
        clearResults();
        fetchProperties();
    });
    stopBtn.addEventListener('click', () => {
        requestController.cancel();
        document.getElementById('error-message').innerText = 'Request cancelled.';
    });

    // Add bioactivity tab click listeners
    document.getElementById('bioactivity-tabs').addEventListener('click', handleTabClick);

    // Show empty state initially
    document.getElementById('bioactivity-empty').style.display = 'block';
});
