const SIGNATURE_PAGE_SIZE = 100;

const params = new URLSearchParams(window.location.search);
const genesParam = params.get('genes');
const diseaseParam = (params.get('disease') || '').trim();
const geneList = genesParam ? genesParam.split(',').filter(g => g.trim()) : [];
let selectedDisease = diseaseParam;

const tbody = document.getElementById('match-tbody');
const emptyState = document.getElementById('match-empty');
const loadingState = document.getElementById('match-loading');
const matchSummary = document.getElementById('match-summary');
const geneInfo = document.getElementById('gene-info');
const errorMsg = document.getElementById('error-message');
const matchBtn = document.getElementById('match-btn');
const scoreBtn = document.getElementById('score-btn');
const scoreContainer = document.getElementById('score-container');
const scoreValue = document.getElementById('score-value');
const scoreGenesCount = document.getElementById('score-genes-count');
const diseaseNameDisplay = document.getElementById('disease-name-display');
const diseaseInput = document.getElementById('disease-input');
const diseaseList = document.getElementById('disease-list');

const sheetThead = document.getElementById('sheet-thead');
const sheetTbody = document.getElementById('sheet-tbody');
const sheetLoading = document.getElementById('sheet-loading');
const sheetEmpty = document.getElementById('sheet-empty');
const sheetError = document.getElementById('sheet-error');

async function fetchDiseaseSignaturePage(disease, page, pageSize) {
    const query = new URLSearchParams({
        disease,
        page: String(page),
        page_size: String(pageSize)
    });
    const response = await fetch(`/api/diseaseSignature/table?${query.toString()}`);

    if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail || `HTTP ${response.status}`);
    }

    return response.json();
}

function showEl(el, shouldShow) {
    if (!el) return;
    el.style.display = shouldShow ? 'block' : 'none';
}

function clearSheetTable() {
    if (sheetThead) sheetThead.innerHTML = '';
    if (sheetTbody) sheetTbody.innerHTML = '';
}

function renderSheetTable(headers, rows) {
    clearSheetTable();
    if (!sheetThead || !sheetTbody) return;

    const headRow = document.createElement('tr');
    headers.forEach(header => {
        const th = document.createElement('th');
        th.textContent = (header == null || header === '') ? '-' : String(header);
        headRow.appendChild(th);
    });
    sheetThead.appendChild(headRow);

    rows.forEach(row => {
        const tr = document.createElement('tr');
        headers.forEach((_, index) => {
            const td = document.createElement('td');
            const value = row[index];
            td.textContent = (value == null || value === '') ? '-' : String(value);
            tr.appendChild(td);
        });
        sheetTbody.appendChild(tr);
    });
}

function updateControlState() {
    const hasGenes = geneList.length > 0;
    const hasDisease = Boolean(selectedDisease);
    matchBtn.disabled = !(hasGenes && hasDisease);

    if (!hasGenes) {
        geneInfo.textContent = 'No gene set found. Go back to Home and search a compound first.';
        emptyState.style.display = 'block';
    } else if (!hasDisease) {
        geneInfo.textContent = `Gene set: ${geneList.length} gene(s). Select a disease to continue.`;
    } else {
        geneInfo.textContent = `Gene set: ${geneList.length} gene(s) - Disease: ${selectedDisease}`;
    }
}

function clearResultsForDiseaseChange() {
    tbody.innerHTML = '';
    emptyState.style.display = geneList.length === 0 ? 'block' : 'none';
    showEl(loadingState, false);
    if (matchSummary) {
        matchSummary.textContent = 'Discarded ambiguous: 0 | Not found: 0';
    }
    scoreBtn.disabled = true;
    if (scoreContainer) scoreContainer.style.display = 'none';
}

async function loadAvailableDiseases() {
    if (!diseaseList) return;
    diseaseList.innerHTML = '';

    try {
        const response = await fetch('/api/diseases');
        if (!response.ok) {
            throw new Error(`Failed to load diseases (HTTP ${response.status})`);
        }

        const data = await response.json();
        const diseases = data.diseases || [];

        if (diseases.length === 0) {
            const option = document.createElement('option');
            option.value = 'No diseases available';
            diseaseList.appendChild(option);
            return;
        }

        diseases.forEach(disease => {
            const option = document.createElement('option');
            option.value = disease;
            diseaseList.appendChild(option);
        });
    } catch (err) {
        console.error('Failed to load diseases:', err);
        const option = document.createElement('option');
        option.value = 'Could not load diseases';
        diseaseList.appendChild(option);
        if (errorMsg) {
            errorMsg.textContent = 'Could not load disease list. Make sure the backend is running and refresh the page.';
        }
    }
}

async function loadDiseaseSignatureTable() {
    if (!selectedDisease) {
        clearSheetTable();
        showEl(sheetLoading, false);
        showEl(sheetError, false);
        showEl(sheetEmpty, true);
        return;
    }

    clearSheetTable();
    showEl(sheetError, false);
    showEl(sheetEmpty, false);
    showEl(sheetLoading, true);

    try {
        const firstPage = await fetchDiseaseSignaturePage(selectedDisease, 1, SIGNATURE_PAGE_SIZE);
        const totalPages = firstPage.totalPages || 1;
        const allRows = [...(firstPage.data || [])];

        for (let page = 2; page <= totalPages; page += 1) {
            const nextPage = await fetchDiseaseSignaturePage(selectedDisease, page, SIGNATURE_PAGE_SIZE);
            allRows.push(...(nextPage.data || []));
        }

        const payload = {
            headers: firstPage.headers || [],
            data: allRows
        };
        const headers = payload.headers || [];
        const data = payload.data || [];

        if (headers.length === 0) {
            showEl(sheetEmpty, true);
            if (sheetError) sheetError.textContent = 'Disease signature has no table headers.';
            showEl(sheetError, true);
            return;
        }

        renderSheetTable(headers, data);
        if (data.length === 0) showEl(sheetEmpty, true);
    } catch (err) {
        if (sheetError) {
            sheetError.textContent = err.message || 'Failed to load disease signature data.';
        }
        showEl(sheetError, true);
    } finally {
        showEl(sheetLoading, false);
    }
}

async function setDisease(diseaseName, shouldLoadTable = true) {
    selectedDisease = (diseaseName || '').trim();
    if (diseaseNameDisplay) {
        diseaseNameDisplay.textContent = selectedDisease || 'Not selected';
    }

    updateControlState();
    clearResultsForDiseaseChange();

    if (shouldLoadTable) {
        await loadDiseaseSignatureTable();
    }
}

async function runMatch() {
    if (geneList.length === 0) {
        errorMsg.textContent = 'No genes available to match.';
        return;
    }
    if (!selectedDisease) {
        errorMsg.textContent = 'Please select a disease first.';
        return;
    }

    errorMsg.textContent = '';
    tbody.innerHTML = '';
    emptyState.style.display = 'none';
    loadingState.style.display = 'block';
    scoreBtn.disabled = true;
    if (scoreContainer) scoreContainer.style.display = 'none';

    try {
        const url = `/api/match?genes=${encodeURIComponent(geneList.join(','))}&disease=${encodeURIComponent(selectedDisease)}`;
        const res = await fetch(url);

        if (!res.ok) {
            const detail = await res.json().catch(() => ({}));
            throw new Error(detail.detail || `HTTP ${res.status}`);
        }

        const json = await res.json();
        loadingState.style.display = 'none';

        const rows = Array.isArray(json.results) ? json.results : [];

        if (matchSummary) {
            const ambiguous = Number.isFinite(json.discarded_ambiguous_count) ? json.discarded_ambiguous_count : 0;
            const notFound = Number.isFinite(json.not_found_count) ? json.not_found_count : 0;
            matchSummary.textContent = `Discarded ambiguous: ${ambiguous} | Not found: ${notFound}`;
        }

        if (rows.length === 0) {
            emptyState.textContent = 'No match results found.';
            emptyState.style.display = 'block';
            return;
        }

        scoreBtn.disabled = false;
        geneInfo.textContent = `Gene set: ${geneList.length} gene(s) - Disease: ${json.disease}`;

        rows.forEach(row => {
            const tr = document.createElement('tr');

            const tdGene = document.createElement('td');
            tdGene.textContent = row.gene;
            tr.appendChild(tdGene);

            const tdClassification = document.createElement('td');
            const classification = row.classification || row.direction || '-';
            tdClassification.textContent = classification;
            if (classification === 'UP') {
                tdClassification.classList.add('text-success');
            } else if (classification === 'DOWN') {
                tdClassification.classList.add('text-danger');
            } else if (classification === 'AMBIGUOUS') {
                tdClassification.classList.add('text-warning');
            }
            tr.appendChild(tdClassification);

            const tdUpCount = document.createElement('td');
            tdUpCount.textContent = String(row.up_count ?? 0);
            tr.appendChild(tdUpCount);

            const tdDownCount = document.createElement('td');
            tdDownCount.textContent = String(row.down_count ?? 0);
            tr.appendChild(tdDownCount);

            const tdRatio = document.createElement('td');
            const ratioValue = Number(row.ratio);
            tdRatio.textContent = Number.isFinite(ratioValue) ? ratioValue.toFixed(2) : '∞';
            tr.appendChild(tdRatio);

            const tdBeneficial = document.createElement('td');
            tdBeneficial.textContent = String(row.beneficial_count ?? 0);
            tdBeneficial.classList.add('text-success');
            tr.appendChild(tdBeneficial);

            const tdHarmful = document.createElement('td');
            tdHarmful.textContent = String(row.harmful_count ?? 0);
            tdHarmful.classList.add('text-danger');
            tr.appendChild(tdHarmful);

            tbody.appendChild(tr);
        });
    } catch (err) {
        loadingState.style.display = 'none';
        errorMsg.textContent = err.message || 'An error occurred.';
    }
}

async function getFinalScore() {
    if (geneList.length === 0 || !selectedDisease) return;

    scoreBtn.disabled = true;
    const originalText = scoreBtn.textContent;
    scoreBtn.textContent = 'Calculating...';
    scoreContainer.style.display = 'none';

    try {
        const url = `/api/finalGeneScore?genes=${encodeURIComponent(geneList.join(','))}&disease=${encodeURIComponent(selectedDisease)}`;
        const res = await fetch(url);

        if (!res.ok) {
            const detail = await res.json().catch(() => ({}));
            throw new Error(detail.detail || 'Failed to calculate score');
        }

        const data = await res.json();
        scoreValue.textContent = typeof data.score === 'number' ? data.score.toFixed(6) : data.score;
        scoreGenesCount.textContent = data.genes_counted ? data.genes_counted.length : 0;
        scoreContainer.style.display = 'block';
    } catch (err) {
        console.error(err);
        alert('Error calculating score: ' + err.message);
    } finally {
        scoreBtn.disabled = false;
        scoreBtn.textContent = originalText;
    }
}

matchBtn.addEventListener('click', runMatch);
scoreBtn.addEventListener('click', getFinalScore);

diseaseInput.addEventListener('input', async () => {
    await setDisease(diseaseInput.value);
});

(async function init() {
    await loadAvailableDiseases();
    if (diseaseParam && diseaseInput) {
        diseaseInput.value = diseaseParam;
    }
    await setDisease(diseaseInput ? diseaseInput.value : '', true);
})();
