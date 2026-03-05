// ── Read gene_set from URL query params ──
const params = new URLSearchParams(window.location.search);
const genesParam = params.get('genes');  // comma-separated
const geneList = genesParam ? genesParam.split(',').filter(g => g.trim()) : [];

// DOM refs
const tbody = document.getElementById('match-tbody');
const emptyState = document.getElementById('match-empty');
const loadingState = document.getElementById('match-loading');
const geneInfo = document.getElementById('gene-info');
const errorMsg = document.getElementById('error-message');
const matchBtn = document.getElementById('match-btn');

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

        // Show which disease was matched
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

// ── Event listeners ──
matchBtn.addEventListener('click', runMatch);

