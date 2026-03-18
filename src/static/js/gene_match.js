// ── Configuration ──
const FIXED_DISEASE_NAME = 'pulmonary hypertension';
const SIGNATURE_PAGE_SIZE = 100;

// ── Read gene_set from URL query params ──
const params = new URLSearchParams(window.location.search);
const genesParam = params.get('genes');
const geneList = genesParam ? genesParam.split(',').filter(g => g.trim()) : [];

// ── Match DOM refs ──
const tbody = document.getElementById('match-tbody');
const emptyState = document.getElementById('match-empty');
const loadingState = document.getElementById('match-loading');
const geneInfo = document.getElementById('gene-info');
const errorMsg = document.getElementById('error-message');
const matchBtn = document.getElementById('match-btn');

// ── Fixed sheet DOM refs ──
const sheetNameLabel = document.getElementById('sheet-name-label');
const sheetThead = document.getElementById('sheet-thead');
const sheetTbody = document.getElementById('sheet-tbody');
const sheetLoading = document.getElementById('sheet-loading');
const sheetEmpty = document.getElementById('sheet-empty');
const sheetError = document.getElementById('sheet-error');

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
        th.textContent = (header == null || header === '') ? '—' : String(header);
        headRow.appendChild(th);
    });
    sheetThead.appendChild(headRow);

    rows.forEach(row => {
        const tr = document.createElement('tr');
        headers.forEach((_, index) => {
            const td = document.createElement('td');
            const value = row[index];
            td.textContent = (value == null || value === '') ? '—' : String(value);
            tr.appendChild(td);
        });
        sheetTbody.appendChild(tr);
    });
}

async function loadFixedSheetData() {
    if (sheetNameLabel) {
        sheetNameLabel.textContent = `Disease: ${FIXED_DISEASE_NAME}`;
    }

    clearSheetTable();
    showEl(sheetError, false);
    showEl(sheetEmpty, false);
    showEl(sheetLoading, true);

    try {
        const query = new URLSearchParams({
            disease: FIXED_DISEASE_NAME,
            page: '1',
            page_size: String(SIGNATURE_PAGE_SIZE)
        });
        const response = await fetch(`/api/diseaseSignature/table?${query.toString()}`);

        if (!response.ok) {
            const detail = await response.json().catch(() => ({}));
            throw new Error(detail.detail || `HTTP ${response.status}`);
        }

        const payload = await response.json();
        const headers = payload.headers || [];
        const data = payload.data || [];

        if (headers.length === 0) {
            showEl(sheetEmpty, true);
            if (sheetError) sheetError.textContent = 'Disease signature has no table headers.';
            showEl(sheetError, true);
            return;
        }

        renderSheetTable(headers, data);
        if (data.length === 0) {
            showEl(sheetEmpty, true);
        }
    } catch (err) {
        if (sheetError) {
            sheetError.textContent = err.message || 'Failed to load disease signature data.';
        }
        showEl(sheetError, true);
    } finally {
        showEl(sheetLoading, false);
    }
}

// Show gene count on load
if (geneList.length > 0) {
    geneInfo.textContent = `Gene set: ${geneList.length} gene(s) — ${geneList.join(', ')}`;
} else {
    geneInfo.textContent = 'No gene set found. Go back to Home and search a compound first.';
    emptyState.style.display = 'block';
}

// ── Fetch match results ──
async function runMatch() {
    if (geneList.length === 0) {
        errorMsg.textContent = 'No genes available to match.';
        return;
    }

    errorMsg.textContent = '';
    tbody.innerHTML = '';
    emptyState.style.display = 'none';
    loadingState.style.display = 'block';

    try {
        const url = `/api/match?genes=${encodeURIComponent(geneList.join(','))}`;
        const res = await fetch(url);

        if (!res.ok) {
            const detail = await res.json();
            throw new Error(detail.detail || `HTTP ${res.status}`);
        }

        const json = await res.json();
        loadingState.style.display = 'none';

        if (!json.results || json.results.length === 0) {
            emptyState.textContent = 'No matching results found.';
            emptyState.style.display = 'block';
            return;
        }

        geneInfo.textContent = `Gene set: ${geneList.length} gene(s) — Disease: ${json.disease}`;

        json.results.forEach(row => {
            const tr = document.createElement('tr');

            const tdGene = document.createElement('td');
            tdGene.textContent = row.gene;
            tr.appendChild(tdGene);

            const tdBeneficial = document.createElement('td');
            tdBeneficial.textContent = row.beneficial;
            tdBeneficial.classList.add('text-success');
            tr.appendChild(tdBeneficial);

            const tdHarmful = document.createElement('td');
            tdHarmful.textContent = row.harmful;
            tdHarmful.classList.add('text-danger');
            tr.appendChild(tdHarmful);

            tbody.appendChild(tr);
        });
    } catch (err) {
        loadingState.style.display = 'none';
        errorMsg.textContent = err.message || 'An error occurred.';
    }
}

// ── Event listeners + initial load ──
matchBtn.addEventListener('click', runMatch);
loadFixedSheetData();
