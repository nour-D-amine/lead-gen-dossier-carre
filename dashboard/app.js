let allLeads = [];

const tableBody = document.getElementById('leads-tbody');
const loader = document.getElementById('loader');
const searchInput = document.getElementById('search-input');

// Side panel elements
const sidePanel = document.getElementById('side-panel');
const panelOverlay = document.getElementById('panel-overlay');
const btnClose = document.getElementById('btn-close-panel');

async function fetchLeads() {
    loader.style.display = 'block';
    tableBody.innerHTML = '';
    
    try {
        const response = await fetch('/api/leads');
        const data = await response.json();
        
        if (data.error) {
            alert('Erreur serveur : ' + data.error);
            return;
        }
        
        allLeads = data.data;
        updateKPIs(allLeads);
        renderTable(allLeads);
    } catch (e) {
        alert('Erreur de connexion au serveur Flask.');
    } finally {
        loader.style.display = 'none';
    }
}

function updateKPIs(leads) {
    document.getElementById('kpi-total').textContent = leads.length;
    
    const withEmail = leads.filter(l => l.Email && l.Email.trim() !== '').length;
    document.getElementById('kpi-emails').textContent = withEmail;
    
    const todo = leads.filter(l => l['Statut Traitement'] === 'À optimiser').length;
    document.getElementById('kpi-todo').textContent = todo;
}

function renderTable(leads) {
    tableBody.innerHTML = '';
    leads.forEach((lead, index) => {
        const tr = document.createElement('tr');
        
        const status = lead['Statut Traitement'] || 'À optimiser';
        const badgeClass = status === 'À optimiser' ? 'status-todo' : 'status-done';
        
        let boamp = lead['Activité BOAMP'] || '';
        if (boamp.length > 50) boamp = boamp.substring(0, 50) + '...';

        tr.innerHTML = `
            <td><span class="status-badge ${badgeClass}">${status}</span></td>
            <td style="font-family: monospace; color: var(--text-dim);">${lead.SIREN}</td>
            <td style="font-weight: 500;">${lead.Nom}</td>
            <td>${lead.NAF}</td>
            <td style="color: var(--text-dim); font-size: 13px;">${boamp}</td>
        `;
        
        tr.addEventListener('click', () => openPanel(lead));
        tableBody.appendChild(tr);
    });
}

function openPanel(lead) {
    document.getElementById('panel-nom').textContent = lead.Nom;
    document.getElementById('panel-dirigeant').textContent = lead.Dirigeant || 'Non renseigné';
    
    const site = lead['Site Web'];
    if (site && site !== '') {
        document.getElementById('panel-site').innerHTML = `<a href="${site}" target="_blank" style="color: var(--primary)">${site}</a>`;
    } else {
        document.getElementById('panel-site').textContent = 'Non renseigné';
    }
    
    document.getElementById('panel-analyse').innerHTML = marked.parse(lead['Analyse Friction'] || 'Aucune analyse');
    document.getElementById('panel-draft').innerHTML = marked.parse(lead['Draft Email'] || 'Aucun brouillon');

    const email = lead.Email;
    const btnMailto = document.getElementById('btn-mailto');
    if (email && email !== '') {
        const subject = encodeURIComponent(`Partenariat - ${lead.Nom}`);
        const body = encodeURIComponent(lead['Draft Email'] || '');
        btnMailto.href = `mailto:${email}?subject=${subject}&body=${body}`;
        btnMailto.style.display = 'flex';
    } else {
        btnMailto.style.display = 'none';
    }

    sidePanel.classList.add('open');
    panelOverlay.classList.add('open');
}

function closePanel() {
    sidePanel.classList.remove('open');
    panelOverlay.classList.remove('open');
}

// Pipeline integration
const btnRunPipeline = document.getElementById('btn-run-pipeline');
const pipelineStatusContainer = document.getElementById('pipeline-status-container');
const pipelineStatusText = document.getElementById('pipeline-status-text');

let statusIntervalId = null;

async function checkPipelineStatus() {
    try {
        const response = await fetch('/api/pipeline/status');
        const data = await response.json();
        
        if (data.running) {
            btnRunPipeline.disabled = true;
            btnRunPipeline.innerHTML = `
                <svg class="spinner" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation: spin 1s linear infinite;"><path d="M21 12a9 9 0 11-6.219-8.56"/></svg>
                Enrichissement...
            `;
            pipelineStatusContainer.style.display = 'flex';
            pipelineStatusText.textContent = data.status;
            
            // Start polling if not already doing so
            if (!statusIntervalId) {
                statusIntervalId = setInterval(checkPipelineStatus, 2000);
            }
        } else {
            // Stop polling
            if (statusIntervalId) {
                clearInterval(statusIntervalId);
                statusIntervalId = null;
            }
            
            btnRunPipeline.disabled = false;
            btnRunPipeline.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                Enrichir les leads (Batch de 5)
            `;
            
            if (data.status && data.status !== "Inactif") {
                pipelineStatusContainer.style.display = 'flex';
                pipelineStatusText.textContent = data.status;
                if (data.error) {
                    alert("Erreur lors de l'enrichissement : " + data.error);
                } else if (data.status.includes("Succès")) {
                    // Refresh data automatically!
                    fetchLeads();
                    setTimeout(() => {
                        pipelineStatusContainer.style.display = 'none';
                    }, 10000);
                }
            } else {
                pipelineStatusContainer.style.display = 'none';
            }
        }
    } catch (e) {
        console.error("Erreur lors de la récupération du statut :", e);
    }
}

async function runPipeline() {
    if (confirm("Voulez-vous lancer l'enrichissement en arrière-plan ? Cela va extraire et enrichir 5 nouveaux leads (environ 2-3 minutes).")) {
        try {
            const response = await fetch('/api/pipeline/run', { method: 'POST' });
            const data = await response.json();
            if (data.error) {
                alert(data.error);
                return;
            }
            // Trigger status check immediately to transition UI
            checkPipelineStatus();
        } catch (e) {
            alert("Impossible de lancer l'enrichissement.");
        }
    }
}

// Event Listeners
document.getElementById('btn-refresh').addEventListener('click', fetchLeads);
btnRunPipeline.addEventListener('click', runPipeline);
btnClose.addEventListener('click', closePanel);
panelOverlay.addEventListener('click', closePanel);

searchInput.addEventListener('input', (e) => {
    const term = e.target.value.toLowerCase();
    const filtered = allLeads.filter(lead => 
        (lead.Nom && lead.Nom.toLowerCase().includes(term)) ||
        (lead.SIREN && lead.SIREN.toString().includes(term)) ||
        (lead['Activité BOAMP'] && lead['Activité BOAMP'].toLowerCase().includes(term))
    );
    renderTable(filtered);
});

// Init
fetchLeads();
checkPipelineStatus(); // Vérifier si un pipeline tourne déjà au chargement de la page
