// Slider normalizzati 0-100 (piu' intuitivi e con passo fine, come richiesto:
// la vecchia scala 20-400 / 10-200 era troppo ampia e a scatti). "Attrazione"
// alta = nodi collegati piu' vicini (distanza del link piu' piccola);
// "Repulsione" alta = nodi che si respingono di piu'.
const DEFAULT_ATTRACTION = 50;
const DEFAULT_REPULSION = 40;
function attractionToLinkDistance(value) {
    return 120 - value; // value 0 -> 120 (lontani), value 100 -> 20 (vicini)
}
function repulsionToChargeStrength(value) {
    return -(value * 3); // value 0 -> 0, value 100 -> -300
}
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
// Stato dei controlli, letto dal canvas reattivo (ridisegnato ad ogni frame).
// Un solo interruttore per TUTTI i nomi (non filtri per tipo, non soglie):
// mostra/nascondi le etichette di tutti i nodi in blocco. Col mouse sopra un
// nodo il nome si vede comunque, sempre.
let showLabels = true;
let hoveredNodeId = null;
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
            // Il pallino c'e' sempre: l'etichetta si vede se i nomi sono attivi
            // (interruttore unico) oppure se il mouse e' su quel nodo.
            if (showLabels || node.id === hoveredNodeId) {
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
        // Applica subito i valori di default degli slider alle forze reali,
        // cosi' cio' che si vede combacia con cio' che gli slider mostrano.
        graph.d3Force("charge")?.strength(repulsionToChargeStrength(DEFAULT_REPULSION));
        graph.d3Force("link")?.distance?.(attractionToLinkDistance(DEFAULT_ATTRACTION));
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
/** "Aggiorna": ricarica SOLO la vista del grafo dal DB. Non fa sognare (tasto
 * separato apposta, vedi initDreamButton): serve a rivedere lo stato attuale
 * senza innescare rielaborazioni. */
function initRefreshButton() {
    const button = document.getElementById("refresh-now-button");
    if (!button)
        return;
    const defaultLabel = button.textContent ?? "Aggiorna";
    button.addEventListener("click", async () => {
        button.disabled = true;
        try {
            await loadAndRender();
            await refreshDreamTimer();
        }
        finally {
            button.disabled = false;
            button.textContent = defaultLabel;
        }
    });
}
/** "Sogna adesso": forza subito un ciclo di sogno, che e' cio' che
 * TRASFORMA quello di cui hai parlato in nuovi nodi/collegamenti. Mostra un
 * riscontro chiaro: se non compaiono nuovi nodi e' perche' non c'era nulla di
 * nuovo da rielaborare dall'ultimo sogno, non perche' l'aggiornamento non
 * funziona (era la confusione segnalata). */
function initDreamButton() {
    const button = document.getElementById("dream-now-button");
    const feedback = document.getElementById("dream-feedback");
    if (!button || !feedback)
        return;
    const defaultLabel = button.textContent ?? "Sogna adesso";
    button.addEventListener("click", async () => {
        button.disabled = true;
        button.textContent = "Sto sognando...";
        feedback.classList.add("hidden");
        try {
            const result = await graphAPI.triggerNow();
            await loadAndRender();
            await refreshDreamTimer();
            feedback.textContent =
                result.consolidated_events > 0
                    ? `Ho rielaborato ${result.consolidated_events} cose: guarda i nuovi nodi.`
                    : "Niente di nuovo da rielaborare (serve aver parlato di qualcosa dall'ultimo sogno).";
            feedback.classList.remove("hidden");
        }
        catch (err) {
            console.error("Sogno manuale fallito:", err);
            feedback.textContent = "Il sogno non e' riuscito, riprova.";
            feedback.classList.remove("hidden");
        }
        finally {
            button.disabled = false;
            button.textContent = defaultLabel;
        }
    });
}
function initShowLabelsToggle() {
    const checkbox = document.getElementById("show-labels");
    if (!checkbox)
        return;
    showLabels = checkbox.checked;
    checkbox.addEventListener("change", () => {
        showLabels = checkbox.checked;
        // Il canvas si ridisegna da solo, ma se la simulazione si e' fermata
        // (grafo stabile) serve un piccolo reheat per vedere subito il cambio.
        graph?.d3ReheatSimulation();
    });
}
function initForceSlider(sliderId, valueId, apply) {
    const slider = document.getElementById(sliderId);
    const valueLabel = document.getElementById(valueId);
    if (!slider)
        return;
    slider.addEventListener("input", () => {
        const value = Number(slider.value);
        if (valueLabel)
            valueLabel.textContent = slider.value;
        apply(value);
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
// Ultimo insight ricevuto (vedi onQuantumInsight in init()): la sola scritta
// "Attiva — iterazione N" non diceva mai COSA il modello stesse facendo in
// quell'iterazione, mentre brain_service quell'informazione la genera gia'
// (campo 'insight' di ogni ciclo Quantum) — semplicemente non arrivava mai
// fino a qui.
let lastQuantumInsight = null;
function renderQuantumStatusText(active, iterationsDone) {
    if (!active)
        return "";
    const base = `Attiva — iterazione ${iterationsDone}. Ascolto e sogni normali sono in pausa.`;
    return lastQuantumInsight ? `${base}\nUltimo collegamento: ${lastQuantumInsight}` : base;
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
        if (!status.active)
            lastQuantumInsight = null;
        statusEl.textContent = renderQuantumStatusText(status.active, status.iterationsDone);
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
    initDreamButton();
    initShowLabelsToggle();
    initForceSlider("attraction", "attraction-value", (v) => graph?.d3Force("link")?.distance?.(attractionToLinkDistance(v)));
    initForceSlider("repulsion", "repulsion-value", (v) => graph?.d3Force("charge")?.strength(repulsionToChargeStrength(v)));
    initQuantumButton();
    refreshDreamTimer();
    setInterval(refreshDreamTimer, 60_000);
    refreshQuantumStatus();
    graphAPI.onQuantumStatusChanged(() => refreshQuantumStatus());
    graphAPI.onQuantumInsight((insight) => {
        lastQuantumInsight = insight;
        refreshQuantumStatus();
    });
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
