const DEFAULT_REPULSION = 120;
const DEFAULT_LINK_DISTANCE = 60;
const EDGE_TYPE_LABELS = {
    conosce: "conosce",
    riguarda: "riguarda",
    e_avvenuto_in: "e' avvenuto in",
    e_collegato_a: "e' collegato a",
};
const NODE_TYPE_COLORS = {
    Persona: "#8ab4ff",
    Evento: "#ffab4a",
    Concetto: "#9b5cff",
    Luogo: "#4affa0",
};
// Stato dei controlli (slider/checkbox): letto sia dagli accessor/canvas
// reattivi (richiamati ad ogni frame) sia dai listener di input.
//
// "Connessioni minime" NON nasconde piu' i pallini (richiesto esplicitamente
// dall'utente dopo che una versione precedente lo faceva per errore): nasconde
// solo l'ETICHETTA di testo dei nodi sotto la soglia, cosi' il grafo resta
// leggibile senza perdere nodi. Passare il mouse su un nodo ne rivela comunque
// sempre il nome, indipendentemente dalla soglia. Nascondere davvero un
// pallino e' invece cosa dei filtri "Filtri" qui sotto (tipo/isolati), che
// sono un'intenzione esplicita e diversa da "nascondi il nome".
let minConnectionsFilter = 0;
let hoveredNodeId = null;
let hideOrphans = false;
const hiddenTypes = new Set();
function computeDegrees(snapshot) {
    const degrees = new Map();
    for (const node of snapshot.nodes)
        degrees.set(node.id, 0);
    for (const edge of snapshot.edges) {
        degrees.set(edge.source_node_id, (degrees.get(edge.source_node_id) ?? 0) + 1);
        degrees.set(edge.target_node_id, (degrees.get(edge.target_node_id) ?? 0) + 1);
    }
    return degrees;
}
function toGraphData(snapshot) {
    const degrees = computeDegrees(snapshot);
    return {
        nodes: snapshot.nodes.map((n) => ({
            id: String(n.id),
            nodeType: n.node_type,
            label: n.label,
            degree: degrees.get(n.id) ?? 0,
        })),
        links: snapshot.edges.map((e) => ({
            source: String(e.source_node_id),
            target: String(e.target_node_id),
            edgeType: e.edge_type,
        })),
    };
}
let graph = null;
let lastSnapshot = null;
function findNodeLabel(id) {
    return lastSnapshot?.nodes.find((n) => n.id === id)?.label ?? `#${id}`;
}
function showNodeDetail(node) {
    const panel = document.getElementById("node-detail");
    const titleEl = document.getElementById("node-detail-title");
    const typeEl = document.getElementById("node-detail-type");
    const connectionsEl = document.getElementById("node-detail-connections");
    if (!panel || !titleEl || !typeEl || !connectionsEl || !lastSnapshot)
        return;
    const nodeId = Number(node.id);
    titleEl.textContent = node.label;
    typeEl.textContent = node.nodeType;
    const outgoing = lastSnapshot.edges
        .filter((e) => e.source_node_id === nodeId)
        .map((e) => `${EDGE_TYPE_LABELS[e.edge_type] ?? e.edge_type} → ${findNodeLabel(e.target_node_id)}`);
    const incoming = lastSnapshot.edges
        .filter((e) => e.target_node_id === nodeId)
        .map((e) => `${findNodeLabel(e.source_node_id)} → ${EDGE_TYPE_LABELS[e.edge_type] ?? e.edge_type}`);
    connectionsEl.innerHTML = "";
    const allConnections = [...outgoing, ...incoming];
    if (allConnections.length === 0) {
        const li = document.createElement("li");
        li.textContent = "Nessuna connessione ancora.";
        li.className = "node-detail-empty";
        connectionsEl.appendChild(li);
    }
    else {
        for (const text of allConnections) {
            const li = document.createElement("li");
            li.textContent = text;
            connectionsEl.appendChild(li);
        }
    }
    panel.classList.remove("hidden");
}
function hideNodeDetail() {
    document.getElementById("node-detail")?.classList.add("hidden");
}
function render(snapshot) {
    const container = document.getElementById("graph-container");
    if (!container)
        return;
    lastSnapshot = snapshot;
    if (!graph) {
        graph = new ForceGraph(container)
            .backgroundColor("#14151f")
            .width(container.clientWidth)
            .height(container.clientHeight)
            .nodeId("id")
            .nodeLabel((node) => `${node.label} (${node.nodeType}, ${node.degree} collegamenti)`)
            .nodeVisibility((node) => !hiddenTypes.has(node.nodeType) && !(hideOrphans && node.degree === 0))
            .linkColor(() => "rgba(255,255,255,0.25)")
            .onNodeClick((node) => showNodeDetail(node))
            .onNodeHover((node) => {
            hoveredNodeId = node?.id ?? null;
        })
            .nodeCanvasObject((node, ctx, scale) => {
            // Raggio in base al numero di collegamenti: piu' un nodo e'
            // centrale nel grafo, piu' risalta a colpo d'occhio.
            const radius = 4 + Math.min(node.degree, 10) * 1.1;
            ctx.beginPath();
            ctx.arc(node.x ?? 0, node.y ?? 0, radius, 0, 2 * Math.PI);
            ctx.fillStyle = NODE_TYPE_COLORS[node.nodeType] ?? "#aaaaaa";
            ctx.fill();
            // Il pallino resta sempre visibile: solo l'etichetta si nasconde
            // sotto la soglia "connessioni minime" (o si rivela comunque al
            // passaggio del mouse), cosi' non si perdono mai nodi dal grafo.
            const showLabel = node.degree >= minConnectionsFilter || node.id === hoveredNodeId;
            if (showLabel) {
                const fontSize = 12 / scale;
                ctx.font = `${fontSize}px "Segoe UI", sans-serif`;
                ctx.textAlign = "center";
                ctx.textBaseline = "top";
                ctx.fillStyle = "rgba(255,255,255,0.85)";
                ctx.fillText(node.label, node.x ?? 0, (node.y ?? 0) + radius + 2);
            }
        })
            .nodePointerAreaPaint((node, color, ctx) => {
            const radius = 4 + Math.min(node.degree, 10) * 1.1;
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(node.x ?? 0, node.y ?? 0, radius + 3, 0, 2 * Math.PI);
            ctx.fill();
        });
        // Applica subito i valori di default degli slider alle forze reali:
        // altrimenti lo slider mostra "120"/"60" ma la simulazione userebbe i
        // default interni di d3-force-graph finche' l'utente non lo tocca,
        // disallineando cio' che si vede da cio' che si legge.
        graph.d3Force("charge")?.strength(-DEFAULT_REPULSION);
        graph.d3Force("link")?.distance?.(DEFAULT_LINK_DISTANCE);
    }
    graph.graphData(toGraphData(snapshot));
}
async function loadAndRender() {
    try {
        const snapshot = await graphAPI.getSnapshot();
        render(snapshot);
    }
    catch (err) {
        // Puo' succedere al primissimo caricamento in background, prima che
        // brain_service sia pronto: non e' un errore fatale, la finestra si
        // riaggiorna comunque ogni volta che viene mostrata (vedi graph-window.ts).
        console.warn("Impossibile caricare il grafo (probabilmente brain_service non e' ancora pronto):", err);
    }
}
function initRefreshButton() {
    const button = document.getElementById("refresh-now-button");
    if (!button)
        return;
    const defaultLabel = button.textContent ?? "Aggiorna adesso";
    button.addEventListener("click", async () => {
        button.disabled = true;
        button.textContent = "Aggiornamento...";
        try {
            await graphAPI.triggerNow();
            // Se ci sono state nuove entita', arriva anche l'evento graph-updated
            // via WS: questa chiamata e' comunque utile per il caso "nessuna novita'",
            // dove quell'evento non scatterebbe mai (vedi consolidation.py).
            await loadAndRender();
        }
        catch (err) {
            console.error("Aggiornamento manuale del grafo fallito:", err);
        }
        finally {
            button.disabled = false;
            button.textContent = defaultLabel;
        }
        await refreshDreamTimer();
    });
}
function initTypeFilters() {
    const container = document.getElementById("type-filter-list");
    if (!container)
        return;
    container.innerHTML = "";
    for (const nodeType of Object.keys(NODE_TYPE_COLORS)) {
        const label = document.createElement("label");
        label.className = "checkbox-row";
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = true;
        checkbox.addEventListener("change", () => {
            if (checkbox.checked)
                hiddenTypes.delete(nodeType);
            else
                hiddenTypes.add(nodeType);
            graph?.d3ReheatSimulation();
        });
        const swatch = document.createElement("span");
        swatch.className = "type-filter-swatch";
        swatch.style.background = NODE_TYPE_COLORS[nodeType];
        label.appendChild(checkbox);
        label.appendChild(swatch);
        label.appendChild(document.createTextNode(nodeType));
        container.appendChild(label);
    }
}
function initHideOrphansToggle() {
    const checkbox = document.getElementById("hide-orphans");
    if (!checkbox)
        return;
    checkbox.addEventListener("change", () => {
        hideOrphans = checkbox.checked;
        graph?.d3ReheatSimulation();
    });
}
function initMinConnectionsSlider() {
    const slider = document.getElementById("min-connections");
    const valueLabel = document.getElementById("min-connections-value");
    if (!slider || !valueLabel)
        return;
    slider.addEventListener("input", () => {
        minConnectionsFilter = Number(slider.value);
        valueLabel.textContent = slider.value;
        // nodeVisibility e' un accessor riletto ad ogni frame, ma se la
        // simulazione si e' gia' fermata (grafo stabile) non ridisegna da sola:
        // un piccolo reheat forza il ricalcolo visibile subito.
        graph?.d3ReheatSimulation();
    });
}
function initRepulsionSlider() {
    const slider = document.getElementById("repulsion");
    if (!slider)
        return;
    slider.addEventListener("input", () => {
        const strength = -Number(slider.value);
        graph?.d3Force("charge")?.strength(strength);
        graph?.d3ReheatSimulation();
    });
}
/** Slider separato per l'attrazione (distanza dei collegamenti), non solo
 * repulsione: prima si poteva solo respingere di piu' o di meno, senza modo
 * di far avvicinare le coppie di nodi collegati. Distanza piu' piccola =
 * nodi collegati tirati piu' vicini, per bilanciare la repulsione generale. */
function initAttractionSlider() {
    const slider = document.getElementById("attraction");
    if (!slider)
        return;
    slider.addEventListener("input", () => {
        const distance = Number(slider.value);
        graph?.d3Force("link")?.distance?.(distance);
        graph?.d3ReheatSimulation();
    });
}
function formatDreamTime(iso) {
    if (!iso)
        return "mai";
    const date = new Date(iso);
    return date.toLocaleString("it-IT", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}
async function refreshDreamTimer() {
    const lastEl = document.getElementById("last-dream-at");
    const nextEl = document.getElementById("next-dream-at");
    if (!lastEl || !nextEl)
        return;
    try {
        const status = await graphAPI.getDreamingStatus();
        lastEl.textContent = formatDreamTime(status.lastDreamAt);
        nextEl.textContent = formatDreamTime(status.nextScheduledAt);
    }
    catch (err) {
        console.warn("Impossibile leggere lo stato del dreaming:", err);
    }
}
async function refreshQuantumStatus() {
    const button = document.getElementById("quantum-button");
    const statusEl = document.getElementById("quantum-status");
    if (!button || !statusEl)
        return;
    try {
        const status = await graphAPI.getQuantumStatus();
        button.textContent = status.active ? "Ferma Quantum" : "Modalita' Quantum";
        button.classList.toggle("active", status.active);
        statusEl.classList.toggle("hidden", !status.active);
        if (status.active) {
            statusEl.textContent = `Attiva — iterazione ${status.iterationsDone}. Ascolto e sogni normali sono in pausa.`;
        }
    }
    catch (err) {
        console.warn("Impossibile leggere lo stato della modalita' Quantum:", err);
    }
}
function initQuantumButton() {
    const button = document.getElementById("quantum-button");
    if (!button)
        return;
    button.addEventListener("click", async () => {
        button.disabled = true;
        try {
            const current = await graphAPI.getQuantumStatus();
            if (current.active) {
                await graphAPI.stopQuantum();
            }
            else {
                await graphAPI.startQuantum();
            }
        }
        catch (err) {
            console.error("Impossibile cambiare stato della modalita' Quantum:", err);
        }
        finally {
            button.disabled = false;
            await refreshQuantumStatus();
        }
    });
}
function init() {
    loadAndRender();
    graphAPI.onUpdated(() => loadAndRender());
    initRefreshButton();
    initTypeFilters();
    initHideOrphansToggle();
    initMinConnectionsSlider();
    initRepulsionSlider();
    initAttractionSlider();
    initQuantumButton();
    refreshDreamTimer();
    setInterval(refreshDreamTimer, 60_000);
    refreshQuantumStatus();
    graphAPI.onQuantumStatusChanged(() => refreshQuantumStatus());
    // Fallback a intervalli mentre e' attiva: gli eventi push coprono
    // avvio/fine, ma il contatore delle iterazioni cresce silenziosamente nel
    // mezzo senza un evento dedicato per ognuna.
    setInterval(refreshQuantumStatus, 5_000);
    document.getElementById("node-detail-close")?.addEventListener("click", () => hideNodeDetail());
    window.addEventListener("resize", () => {
        const container = document.getElementById("graph-container");
        if (container && graph) {
            graph.width(container.clientWidth).height(container.clientHeight);
        }
    });
}
init();
export {};
