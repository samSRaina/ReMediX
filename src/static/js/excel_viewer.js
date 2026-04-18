// ── Configuration ──
const PAGE_SIZE = 100;

// ── DOM References ──
const loadingContainer = document.getElementById('loading-container');
const errorContainer   = document.getElementById('error-container');
const tabsNav          = document.getElementById('excel-tabs-nav');
const tabsContent      = document.getElementById('excel-tabs-content');
const stopBtn          = document.getElementById('excel-stop-btn');
const requestController = createRequestController({
    runButtons: [],
    cancelButton: stopBtn
});

// ── State ──
let sheetNames = [];
let sheetMeta  = {};            // { sheetName: { headers, totalRows } }
let sheetState = {};            // { sheetName: { page } }
let activeSheet = null;

// ── Initialize ──
document.addEventListener('DOMContentLoaded', () => loadMeta());

// ── 1. Fetch lightweight metadata (sheet names + headers + row counts) ──
async function loadMeta() {
    const request = requestController.begin();
    const signal = request.signal;
    try {
        showLoading();
        const res = await fetch('/api/excelData/meta', { signal });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();

        sheetNames = json.sheetNames || [];
        sheetMeta  = json.meta || {};

        if (sheetNames.length === 0) throw new Error('No sheets found');

        sheetNames.forEach(n => { sheetState[n] = { page: 1 }; });

        hideLoading();
        renderTabs();
        activateTab(sheetNames[0]);
    } catch (err) {
        if (err.name === 'AbortError') {
            hideLoading();
            showError('Loading cancelled.');
            return;
        }
        console.error(err);
        hideLoading();
        showError(err.message);
    } finally {
        requestController.end(request);
    }
}

// ── 2. Fetch one page of a sheet ──
async function fetchPage(sheetName, page, signal) {
    const params = new URLSearchParams({ name: sheetName, page, page_size: PAGE_SIZE });
    const res = await fetch(`/api/excelData/sheet?${params}`, { signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
}

// ── 3. Tabs ──
function renderTabs() {
    tabsNav.innerHTML = '';
    sheetNames.forEach(name => {
        const tab = document.createElement('div');
        tab.className = 'excel-tab';
        tab.textContent = name.trim();
        tab.dataset.sheet = name;
        tab.addEventListener('click', () => activateTab(name));
        tabsNav.appendChild(tab);
    });
}

async function activateTab(sheetName) {
    activeSheet = sheetName;

    // highlight tab
    document.querySelectorAll('.excel-tab').forEach(t => t.classList.toggle('active', t.dataset.sheet === sheetName));

    // ensure container exists
    let container = tabsContent.querySelector(`[data-sheet="${sheetName}"]`);
    if (!container) {
        container = document.createElement('div');
        container.className = 'excel-tab-content';
        container.dataset.sheet = sheetName;
        tabsContent.appendChild(container);
    }

    // show only the active container
    tabsContent.querySelectorAll('.excel-tab-content').forEach(c => c.classList.toggle('active', c.dataset.sheet === sheetName));

    // load the current page for this sheet
    await loadSheetPage(sheetName, sheetState[sheetName].page);
}

// ── 4. Load + render one page ──
async function loadSheetPage(sheetName, page) {
    const container = tabsContent.querySelector(`[data-sheet="${sheetName}"]`);
    if (!container) return;
    const request = requestController.begin();
    const signal = request.signal;

    // show inline loading
    container.innerHTML = '<div class="loading-spinner"><div class="spinner-border spinner-border-sm" role="status"></div><p class="mt-2">Loading…</p></div>';

    try {
        const json = await fetchPage(sheetName, page, signal);
        sheetState[sheetName].page = json.page;
        renderSheet(container, sheetName, json);
    } catch (err) {
        if (err.name === 'AbortError') {
            container.innerHTML = '<div class="text-muted fst-italic py-2">Loading cancelled.</div>';
            return;
        }
        container.innerHTML = `<div class="error-message"><strong>Error:</strong> ${err.message}</div>`;
    } finally {
        requestController.end(request);
    }
}

function renderSheet(container, sheetName, json) {
    const { headers, data, page, pageSize, total, totalPages } = json;
    container.innerHTML = '';

    // ── info bar ──
    const info = document.createElement('div');
    info.className = 'excel-info-bar';
    const start = (page - 1) * pageSize + 1;
    const end   = Math.min(page * pageSize, total);
    info.innerHTML = `<small>Showing <strong>${start.toLocaleString()}–${end.toLocaleString()}</strong> of <strong>${total.toLocaleString()}</strong> rows  ·  ${headers.length} columns</small>`;
    container.appendChild(info);

    // ── table ──
    const wrapper = document.createElement('div');
    wrapper.className = 'excel-table-wrapper';

    const table = document.createElement('table');
    table.className = 'excel-table';

    // thead
    const thead = document.createElement('thead');
    const hRow  = document.createElement('tr');
    headers.forEach(h => {
        const th = document.createElement('th');
        th.textContent = (h != null ? String(h) : '').trim() || '—';
        hRow.appendChild(th);
    });
    thead.appendChild(hRow);
    table.appendChild(thead);

    // tbody
    const tbody = document.createElement('tbody');
    data.forEach(row => {
        const tr = document.createElement('tr');
        headers.forEach((_, ci) => {
            const td = document.createElement('td');
            const v  = row[ci];
            td.textContent = (v === null || v === undefined || v === '') ? '—' : String(v);
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    wrapper.appendChild(table);
    container.appendChild(wrapper);

    // ── pagination ──
    if (totalPages > 1) {
        container.appendChild(buildPagination(sheetName, page, totalPages));
    }
}

// ── 5. Pagination controls ──
function buildPagination(sheetName, currentPage, totalPages) {
    const nav = document.createElement('nav');
    nav.className = 'mt-3';
    nav.setAttribute('aria-label', `${sheetName} pagination`);

    const ul = document.createElement('ul');
    ul.className = 'pagination justify-content-center mb-0';

    const addItem = (label, targetPage, disabled, active) => {
        const li = document.createElement('li');
        li.className = `page-item${disabled ? ' disabled' : ''}${active ? ' active' : ''}`;
        const a = document.createElement('a');
        a.className = 'page-link';
        a.href = '#';
        a.textContent = label;
        if (!disabled && !active) {
            a.addEventListener('click', e => {
                e.preventDefault();
                sheetState[sheetName].page = targetPage;
                loadSheetPage(sheetName, targetPage);
            });
        }
        li.appendChild(a);
        ul.appendChild(li);
    };

    // Previous
    addItem('‹', currentPage - 1, currentPage === 1, false);

    // Page numbers (show a window of pages)
    const maxVisible = 7;
    let startPage = Math.max(1, currentPage - Math.floor(maxVisible / 2));
    let endPage   = Math.min(totalPages, startPage + maxVisible - 1);
    if (endPage - startPage + 1 < maxVisible) {
        startPage = Math.max(1, endPage - maxVisible + 1);
    }

    if (startPage > 1) {
        addItem('1', 1, false, false);
        if (startPage > 2) {
            addItem('…', 0, true, false);
        }
    }

    for (let p = startPage; p <= endPage; p++) {
        addItem(String(p), p, false, p === currentPage);
    }

    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            addItem('…', 0, true, false);
        }
        addItem(String(totalPages), totalPages, false, false);
    }

    // Next
    addItem('›', currentPage + 1, currentPage === totalPages, false);

    nav.appendChild(ul);
    return nav;
}

// ── 6. Loading / Error helpers ──
function showLoading() {
    loadingContainer.style.display = 'block';
    tabsNav.innerHTML = '';
    tabsContent.innerHTML = '';
}

function hideLoading() {
    loadingContainer.style.display = 'none';
}

function showError(message) {
    errorContainer.innerHTML = '';
    const div = document.createElement('div');
    div.className = 'error-message';
    div.innerHTML = `<strong>Error:</strong> ${message}`;
    errorContainer.appendChild(div);
}

stopBtn.addEventListener('click', () => requestController.cancel());
