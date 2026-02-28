// ── State ──
let currentPage = 1;
let currentSearch = '';
let currentPageSize = 50;

// ── DOM References ──
const tbody = document.getElementById('gene-tbody');
const emptyState = document.getElementById('gene-empty');
const loadingState = document.getElementById('gene-loading');
const resultsInfo = document.getElementById('results-info');
const pagination = document.getElementById('pagination');
const searchInput = document.getElementById('gene-search');
const searchBtn = document.getElementById('search-btn');
const clearBtn = document.getElementById('clear-btn');
const pageSizeSelect = document.getElementById('page-size-select');

// ── Fetch Data ──
async function fetchGeneData(page, search, pageSize) {
    loadingState.style.display = 'block';
    emptyState.style.display = 'none';
    tbody.innerHTML = '';

    const params = new URLSearchParams({ page, page_size: pageSize });
    if (search) params.set('search', search);

    try {
        const res = await fetch(`/api/geneExpressions?${params}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();

        loadingState.style.display = 'none';

        if (!json.data || json.data.length === 0) {
            emptyState.style.display = 'block';
            resultsInfo.textContent = 'No results found.';
            pagination.innerHTML = '';
            return;
        }

        renderTable(json.data);
        renderPagination(json.page, json.total_pages, json.total);

        const start = (json.page - 1) * json.page_size + 1;
        const end = Math.min(json.page * json.page_size, json.total);
        resultsInfo.textContent = `Showing ${start}–${end} of ${json.total.toLocaleString()} records`;

    } catch (err) {
        console.error('Fetch error:', err);
        loadingState.style.display = 'none';
        emptyState.textContent = 'Error loading data. Please try again.';
        emptyState.style.display = 'block';
    }
}

// ── Render Table Rows ──
function renderTable(rows) {
    tbody.innerHTML = '';
    rows.forEach(row => {
        const tr = document.createElement('tr');
        tr.classList.add('gene-row');
        tr.dataset.gene = row['Gene.symbol'] || '';

        const cols = ['ID', 'adj.P.Val', 'logFC', 'Gene.symbol'];
        cols.forEach(col => {
            const td = document.createElement('td');
            const val = row[col];

            if (col === 'adj.P.Val' && val != null) {
                td.textContent = Number(val).toExponential(2);
            } else if (col === 'logFC' && val != null) {
                td.textContent = Number(val).toFixed(6);
                // Color code: green for positive logFC, red for negative
                if (val > 0) td.classList.add('text-success');
                else if (val < 0) td.classList.add('text-danger');
            } else {
                td.textContent = val ?? '—';
            }

            tr.appendChild(td);
        });

        // Clickable row → navigate to gene analysis (placeholder route)
        tr.addEventListener('click', () => {
            const gene = row['Gene.symbol'];
            if (gene) {
                // Navigate to gene analysis page (to be expanded upon)
                window.location.href = `/geneAnalysis?gene=${encodeURIComponent(gene)}`;
            }
        });

        tbody.appendChild(tr);
    });
}

// ── Render Pagination ──
function renderPagination(page, totalPages, total) {
    pagination.innerHTML = '';

    if (totalPages <= 1) return;

    // Helper to create a page item
    function addPageItem(label, targetPage, isActive = false, isDisabled = false) {
        const li = document.createElement('li');
        li.className = `page-item${isActive ? ' active' : ''}${isDisabled ? ' disabled' : ''}`;
        const a = document.createElement('a');
        a.className = 'page-link';
        a.href = '#';
        a.textContent = label;
        if (!isDisabled && !isActive) {
            a.addEventListener('click', (e) => {
                e.preventDefault();
                currentPage = targetPage;
                fetchGeneData(currentPage, currentSearch, currentPageSize);
                window.scrollTo({ top: 0, behavior: 'smooth' });
            });
        }
        li.appendChild(a);
        pagination.appendChild(li);
    }

    // Previous
    addPageItem('«', page - 1, false, page === 1);

    // Page numbers — show a window around current page
    const maxVisible = 7;
    let startPage = Math.max(1, page - Math.floor(maxVisible / 2));
    let endPage = Math.min(totalPages, startPage + maxVisible - 1);
    if (endPage - startPage < maxVisible - 1) {
        startPage = Math.max(1, endPage - maxVisible + 1);
    }

    if (startPage > 1) {
        addPageItem('1', 1);
        if (startPage > 2) {
            const li = document.createElement('li');
            li.className = 'page-item disabled';
            li.innerHTML = '<span class="page-link">…</span>';
            pagination.appendChild(li);
        }
    }

    for (let i = startPage; i <= endPage; i++) {
        addPageItem(i, i, i === page);
    }

    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            const li = document.createElement('li');
            li.className = 'page-item disabled';
            li.innerHTML = '<span class="page-link">…</span>';
            pagination.appendChild(li);
        }
        addPageItem(totalPages, totalPages);
    }

    // Next
    addPageItem('»', page + 1, false, page === totalPages);
}

// ── Event Listeners ──

// Search
searchBtn.addEventListener('click', () => {
    currentSearch = searchInput.value.trim();
    currentPage = 1;
    fetchGeneData(currentPage, currentSearch, currentPageSize);
});

searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        searchBtn.click();
    }
});

// Clear
clearBtn.addEventListener('click', () => {
    searchInput.value = '';
    currentSearch = '';
    currentPage = 1;
    fetchGeneData(currentPage, currentSearch, currentPageSize);
});

// Page size change
pageSizeSelect.addEventListener('change', () => {
    currentPageSize = parseInt(pageSizeSelect.value);
    currentPage = 1;
    fetchGeneData(currentPage, currentSearch, currentPageSize);
});

// ── Initial Load ──
fetchGeneData(currentPage, currentSearch, currentPageSize);

