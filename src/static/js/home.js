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
            const responseDrugbank = await fetch(`/api/drugbank/inchikey/${pubchemData.InChIKey}`);
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
});

