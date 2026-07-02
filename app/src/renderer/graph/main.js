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
function toGraphData(snapshot) {
    return {
        nodes: snapshot.nodes.map((n) => ({ id: String(n.id), nodeType: n.node_type, label: n.label })),
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
            .nodeLabel((node) => `${node.label} (${node.nodeType})`)
            .linkColor(() => "rgba(255,255,255,0.25)")
            .onNodeClick((node) => showNodeDetail(node))
            .nodeCanvasObject((node, ctx, scale) => {
            const radius = 5;
            ctx.beginPath();
            ctx.arc(node.x ?? 0, node.y ?? 0, radius, 0, 2 * Math.PI);
            ctx.fillStyle = NODE_TYPE_COLORS[node.nodeType] ?? "#aaaaaa";
            ctx.fill();
            const fontSize = 12 / scale;
            ctx.font = `${fontSize}px "Segoe UI", sans-serif`;
            ctx.textAlign = "center";
            ctx.textBaseline = "top";
            ctx.fillStyle = "rgba(255,255,255,0.85)";
            ctx.fillText(node.label, node.x ?? 0, (node.y ?? 0) + radius + 2);
        })
            .nodePointerAreaPaint((node, color, ctx) => {
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(node.x ?? 0, node.y ?? 0, 8, 0, 2 * Math.PI);
            ctx.fill();
        });
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
    });
}
function init() {
    loadAndRender();
    graphAPI.onUpdated(() => loadAndRender());
    initRefreshButton();
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
