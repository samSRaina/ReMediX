const SIGNATURE_PAGE_SIZE = 100;
const POLL_INTERVAL_MS = 700;

const params = new URLSearchParams(window.location.search);
const genesParam = params.get('genes');
const diseaseParam = (params.get('disease') || '').trim();
const geneList = genesParam ? genesParam.split(',').filter(g => g.trim()) : [];
let selectedDisease = diseaseParam;
let activeJobId = null;
let diseaseInputTimer = null;

const tbody = document.getElementById('match-tbody');
const emptyState = document.getElementById('match-empty');
const loadingState = document.getElementById('match-loading');
const matchSummary = document.getElementById('match-summary');
const geneInfo = document.getElementById('gene-info');
const errorMsg = document.getElementById('error-message');
const matchBtn = document.getElementById('match-btn');
const scoreBtn = document.getElementById('score-btn');
const stopBtn = document.getElementById('stop-btn');
const scoreContainer = document.getElementById('score-container');
const scoreValue = document.getElementById('score-value');
const scoreGenesCount = document.getElementById('score-genes-count');
const scoreInterpretation = document.getElementById('score-interpretation');
const scoreCoverage = document.getElementById('score-coverage');
const diseaseNameDisplay = document.getElementById('disease-name-display');
const diseaseInput = document.getElementById('disease-input');
const diseaseList = document.getElementById('disease-list');

const sheetThead = document.getElementById('sheet-thead');
const sheetTbody = document.getElementById('sheet-tbody');
const sheetLoading = document.getElementById('sheet-loading');
const sheetEmpty = document.getElementById('sheet-empty');
const sheetError = document.getElementById('sheet-error');
const sheetPageMeta = document.getElementById('sheet-page-meta');

const requestController = createRequestController({
    runButtons: [matchBtn, scoreBtn],
    cancelButton: stopBtn
});

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
    if (matchSummary) matchSummary.textContent = 'Discarded ambiguous: 0 | Not found: 0';
    scoreBtn.disabled = true;
    if (scoreContainer) scoreContainer.style.display = 'none';
}

function createAbortError() {
    const error = new Error('Request cancelled.');
    error.name = 'AbortError';
    return error;
}

async function waitWithAbort(ms, signal) {
    await new Promise((resolve, reject) => {
        const timer = setTimeout(resolve, ms);
        if (!signal) return;
        signal.addEventListener('abort', () => {
            clearTimeout(timer);
            reject(createAbortError());
        }, { once: true });
    });
}

async function cancelActiveJob() {
    if (!activeJobId) return;
    const jobId = activeJobId;
    activeJobId = null;
    try {
        await fetch(`/api/jobs/${encodeURIComponent(jobId)}/cancel`, { method: 'POST' });
    } catch (_) {
        // best-effort cancellation
    }
}

async function runJobAndGetResult(endpoint, payload, request) {
    await cancelActiveJob();
    const signal = request.signal;

    const startRes = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal
    });

    if (!startRes.ok) {
        const detail = await startRes.json().catch(() => ({}));
        throw new Error(detail.detail || `HTTP ${startRes.status}`);
    }

    const startPayload = await startRes.json();
    const jobId = startPayload.job_id;
    activeJobId = jobId;

    try {
        while (true) {
            if (signal.aborted) throw createAbortError();

            const statusRes = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`, { signal });
            if (!statusRes.ok) throw new Error(`Failed to fetch job status (HTTP ${statusRes.status})`);
            const statusPayload = await statusRes.json();

            if (statusPayload.status === 'completed') {
                const resultRes = await fetch(`/api/jobs/${encodeURIComponent(jobId)}/result`, { signal });
                if (!resultRes.ok) {
                    const detail = await resultRes.json().catch(() => ({}));
                    throw new Error(detail.detail || `Failed to fetch job result (HTTP ${resultRes.status})`);
                }
                const resultPayload = await resultRes.json();
                return resultPayload.result;
            }

            if (statusPayload.status === 'failed') {
                throw new Error(statusPayload.error || 'Job failed');
            }
            if (statusPayload.status === 'cancelled') {
                throw createAbortError();
            }

            await waitWithAbort(POLL_INTERVAL_MS, signal);
        }
    } finally {
        if (activeJobId === jobId) activeJobId = null;
    }
}

async function loadAvailableDiseases() {
    if (!diseaseList) return;
    diseaseList.innerHTML = '';

    try {
        const response = await fetch('/api/diseases');
        if (!response.ok) throw new Error(`Failed to load diseases (HTTP ${response.status})`);

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
        if (errorMsg) errorMsg.textContent = 'Could not load disease list. Refresh the page.';
    }
}

async function loadDiseaseSignatureTable() {
    if (!selectedDisease) {
        clearSheetTable();
        showEl(sheetLoading, false);
        showEl(sheetError, false);
        showEl(sheetEmpty, true);
        if (sheetPageMeta) sheetPageMeta.textContent = '';
        return;
    }

    clearSheetTable();
    showEl(sheetError, false);
    showEl(sheetEmpty, false);
    showEl(sheetLoading, true);

    const request = requestController.begin();
    try {
        const payload = await runJobAndGetResult('/api/jobs/diseaseSignatureTable', {
            disease: selectedDisease,
            page: 1,
            page_size: SIGNATURE_PAGE_SIZE
        }, request);

        const headers = payload.headers || [];
        const data = payload.data || [];

        if (headers.length === 0) {
            showEl(sheetEmpty, true);
            if (sheetError) sheetError.textContent = 'Disease signature has no table headers.';
            showEl(sheetError, true);
            return;
        }

        renderSheetTable(headers, data);
        if (sheetPageMeta) {
            sheetPageMeta.textContent = `Showing page ${payload.page} of ${payload.totalPages} (${payload.total} total rows).`;
        }
        if (data.length === 0) showEl(sheetEmpty, true);
    } catch (err) {
        if (err.name === 'AbortError') {
            if (sheetError) sheetError.textContent = 'Loading cancelled.';
        } else if (sheetError) {
            sheetError.textContent = err.message || 'Failed to load disease signature data.';
        }
        showEl(sheetError, true);
    } finally {
        showEl(sheetLoading, false);
        requestController.end(request);
    }
}

async function setDisease(diseaseName, shouldLoadTable = true) {
    selectedDisease = (diseaseName || '').trim();
    if (diseaseNameDisplay) diseaseNameDisplay.textContent = selectedDisease || 'Not selected';

    updateControlState();
    clearResultsForDiseaseChange();

    if (shouldLoadTable) await loadDiseaseSignatureTable();
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

    const request = requestController.begin();
    try {
        const json = await runJobAndGetResult('/api/jobs/match', {
            genes: geneList,
            disease: selectedDisease
        }, request);

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
            if (classification === 'UP') tdClassification.classList.add('text-success');
            else if (classification === 'DOWN') tdClassification.classList.add('text-danger');
            else if (classification === 'AMBIGUOUS') tdClassification.classList.add('text-warning');
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
        if (err.name === 'AbortError') errorMsg.textContent = 'Match cancelled.';
        else errorMsg.textContent = err.message || 'An error occurred.';
    } finally {
        loadingState.style.display = 'none';
        requestController.end(request);
    }
}

async function getFinalScore() {
    if (geneList.length === 0 || !selectedDisease) return;

    const originalText = scoreBtn.textContent;
    scoreBtn.textContent = 'Calculating...';
    scoreContainer.style.display = 'none';

    const request = requestController.begin();
    try {
        const data = await runJobAndGetResult('/api/jobs/finalGeneScore', {
            genes: geneList,
            disease: selectedDisease
        }, request);

        scoreValue.textContent = typeof data.score === 'number' ? data.score.toFixed(6) : data.score;
        scoreGenesCount.textContent = data.genes_counted ? data.genes_counted.length : 0;
        if (scoreInterpretation) scoreInterpretation.textContent = `Interpretation: ${data.interpretation || '-'}`;
        if (scoreCoverage) {
            const coverageValue = Number(data.coverage);
            scoreCoverage.textContent = Number.isFinite(coverageValue)
                ? `Coverage: ${(coverageValue * 100).toFixed(1)}%`
                : 'Coverage: -';
        }
        scoreContainer.style.display = 'block';
    } catch (err) {
        if (err.name === 'AbortError') errorMsg.textContent = 'Score calculation cancelled.';
        else alert('Error calculating score: ' + err.message);
    } finally {
        scoreBtn.textContent = originalText;
        requestController.end(request);
        updateControlState();
    }
}

matchBtn.addEventListener('click', runMatch);
scoreBtn.addEventListener('click', getFinalScore);
stopBtn.addEventListener('click', async () => {
    requestController.cancel();
    await cancelActiveJob();
    showEl(loadingState, false);
    showEl(sheetLoading, false);
    errorMsg.textContent = 'Request cancelled.';
});

diseaseInput.addEventListener('input', () => {
    clearTimeout(diseaseInputTimer);
    diseaseInputTimer = setTimeout(async () => {
        await setDisease(diseaseInput.value);
    }, 400);
});

(async function init() {
    await loadAvailableDiseases();
    if (diseaseParam && diseaseInput) diseaseInput.value = diseaseParam;
    await setDisease(diseaseInput ? diseaseInput.value : '', true);
})();

