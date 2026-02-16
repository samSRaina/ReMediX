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

// Bioactivity table columns
const BIOACTIVITY_COLUMNS = [
    'target_chembl_id',
    'target_name',
    'target_type',
    'target_organism',
    'standard_type',
    'standard_value',
    'standard_units'
];

// Fetch and display bioactivity data
async function fetchBioactivity(inchiKey, standardType) {
    const tbody = document.getElementById('bioactivity-tbody');
    const emptyState = document.getElementById('bioactivity-empty');

    // Clear existing data
    tbody.innerHTML = '';
    emptyState.classList.remove('show');

    if (!inchiKey) {
        emptyState.classList.add('show');
        return;
    }

    try {
        const url = `/api/chembl/inchikey/${inchiKey}/bioactivity?standard_type=${standardType}`;
        const response = await fetch(url);

        if (!response.ok) {
            emptyState.classList.add('show');
            return;
        }

        const data = await response.json();

        if (!data || data.length === 0) {
            emptyState.classList.add('show');
            return;
        }

        // Populate table rows
        data.forEach(row => {
            const tr = document.createElement('tr');
            BIOACTIVITY_COLUMNS.forEach(col => {
                const td = document.createElement('td');
                td.textContent = row[col] || '-';
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });

    } catch (err) {
        console.error('Bioactivity fetch error:', err);
        emptyState.classList.add('show');
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
    fetchBioactivity(currentInChIKey, currentBioactivityType);
}

// Clear bioactivity table
function clearBioactivity() {
    document.getElementById('bioactivity-tbody').innerHTML = '';
    document.getElementById('bioactivity-empty').classList.add('show');
    currentInChIKey = null;
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
async function fetchProperties() {
    const input = document.getElementById('compound-input').value.trim();
    if (!input) {
        showError('Please enter a compound name or SMILE');
        return;
    }

    const isSmileSearch = document.getElementById('searchbar-toggle').checked;
    const endpoint = isSmileSearch
        ? `/api/compound/smile/${encodeURIComponent(input)}/properties`
        : `/api/compound/name/${encodeURIComponent(input)}/properties`;

    try {
        // First fetch PubChem to get InChIKey
        const responsePubchem = await fetch(endpoint);
        if (!responsePubchem.ok) {
            throw new Error('Compound not found or API error');
        }

        const pubchemData = await responsePubchem.json();

        // Fetch DrugBank in parallel if InChIKey exists
        let drugbankData = null;
        if (pubchemData.InChIKey) {
            const responseDrugbank = await fetch(`/api/drugbank/inchikey/${pubchemData.InChIKey}/properties`);
            if (responseDrugbank.ok) {
                drugbankData = await responseDrugbank.json();
            }
        }

        // Display both datasets together
        displayPubchemData(pubchemData, input);
        if (drugbankData) {
            displayDrugbankData(drugbankData);
        } else {
            clearDrugbankData();
        }

        // Fetch bioactivity data if InChIKey exists
        if (pubchemData.InChIKey) {
            currentInChIKey = pubchemData.InChIKey;
            fetchBioactivity(currentInChIKey, currentBioactivityType);
        } else {
            clearBioactivity();
        }

    } catch (err) {
        showError(err.message || 'An error occurred.');
    }
}

// Initialize event listeners when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('home-form').addEventListener('submit', (e) => {
        e.preventDefault();
        document.getElementById('error-message').innerText = '';
        clearResults();
        fetchProperties();
    });

    // Add bioactivity tab click listeners
    document.querySelector('.bioactivity-tabs').addEventListener('click', handleTabClick);

    // Show empty state initially
    document.getElementById('bioactivity-empty').classList.add('show');
});

