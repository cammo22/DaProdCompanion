/**
 * Script del pannello "cervellone", caricato come modulo ES. Usa force-graph
 * caricato prima come script classico (vedi index.html): espone un globale
 * ForceGraph, niente bundler/React necessari solo per questo pannello.
 */
export {};

interface GraphNode {
  id: number;
  node_type: string;
  label: string;
}

interface GraphEdge {
  id: number;
  source_node_id: number;
  target_node_id: number;
  edge_type: string;
}

interface GraphSnapshot {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

interface RenderNode {
  id: string;
  nodeType: string;
  label: string;
  degree: number;
  x?: number;
  y?: number;
}

interface DreamingStatus {
  lastDreamAt: string | null;
  nextScheduledAt: string | null;
}

interface QuantumStatus {
  active: boolean;
  iterationsDone: number;
}

declare const graphAPI: {
  getSnapshot(): Promise<GraphSnapshot>;
  onUpdated(callback: () => void): void;
  triggerNow(): Promise<{ consolidated_events: number }>;
  getDreamingStatus(): Promise<DreamingStatus>;
  startQuantum(): Promise<QuantumStatus>;
  stopQuantum(): Promise<QuantumStatus>;
  getQuantumStatus(): Promise<QuantumStatus>;
  onQuantumStatusChanged(callback: () => void): void;
};

interface D3Force {
  strength(value: number): void;
  distance?(value: number): void;
}

const DEFAULT_REPULSION = 120;
const DEFAULT_LINK_DISTANCE = 60;

declare class ForceGraph {
  constructor(element: HTMLElement);
  graphData(data: { nodes: RenderNode[]; links: { source: string; target: string; edgeType: string }[] }): this;
  nodeId(id: string): this;
  nodeLabel(accessor: (node: RenderNode) => string): this;
  nodeVisibility(accessor: (node: RenderNode) => boolean): this;
  linkColor(accessor: () => string): this;
  nodeCanvasObject(fn: (node: RenderNode, ctx: CanvasRenderingContext2D, scale: number) => void): this;
  nodePointerAreaPaint(
    fn: (node: RenderNode, color: string, ctx: CanvasRenderingContext2D, scale: number) => void,
  ): this;
  onNodeClick(callback: (node: RenderNode) => void): this;
  onNodeHover(callback: (node: RenderNode | null) => void): this;
  backgroundColor(color: string): this;
  width(w: number): this;
  height(h: number): this;
  d3Force(forceName: string): D3Force | undefined;
  d3ReheatSimulation(): this;
}

const EDGE_TYPE_LABELS: Record<string, string> = {
  conosce: "conosce",
  riguarda: "riguarda",
  e_avvenuto_in: "e' avvenuto in",
  e_collegato_a: "e' collegato a",
};

const NODE_TYPE_COLORS: Record<string, string> = {
  Persona: "#8ab4ff",
  Evento: "#ffab4a",
  Concetto: "#9b5cff",
  Luogo: "#4affa0",
};

// Stato dei controlli (slider): letto sia dagli accessor/canvas reattivi
// (richiamati ad ogni frame) sia dai listener di input.
//
// "Connessioni minime" NON nasconde piu' i pallini (richiesto esplicitamente
// dall'utente dopo che una versione precedente lo faceva per errore): nasconde
// solo l'ETICHETTA di testo dei nodi sotto la soglia, cosi' il grafo resta
// leggibile senza perdere nodi. Passare il mouse su un nodo ne rivela comunque
// sempre il nome, indipendentemente dalla soglia.
let minConnectionsFilter = 0;
let hoveredNodeId: string | null = null;

function computeDegrees(snapshot: GraphSnapshot): Map<number, number> {
  const degrees = new Map<number, number>();
  for (const node of snapshot.nodes) degrees.set(node.id, 0);
  for (const edge of snapshot.edges) {
    degrees.set(edge.source_node_id, (degrees.get(edge.source_node_id) ?? 0) + 1);
    degrees.set(edge.target_node_id, (degrees.get(edge.target_node_id) ?? 0) + 1);
  }
  return degrees;
}

function toGraphData(snapshot: GraphSnapshot) {
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

let graph: ForceGraph | null = null;
let lastSnapshot: GraphSnapshot | null = null;

function findNodeLabel(id: number): string {
  return lastSnapshot?.nodes.find((n) => n.id === id)?.label ?? `#${id}`;
}

function showNodeDetail(node: RenderNode): void {
  const panel = document.getElementById("node-detail");
  const titleEl = document.getElementById("node-detail-title");
  const typeEl = document.getElementById("node-detail-type");
  const connectionsEl = document.getElementById("node-detail-connections");
  if (!panel || !titleEl || !typeEl || !connectionsEl || !lastSnapshot) return;

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
  } else {
    for (const text of allConnections) {
      const li = document.createElement("li");
      li.textContent = text;
      connectionsEl.appendChild(li);
    }
  }

  panel.classList.remove("hidden");
}

function hideNodeDetail(): void {
  document.getElementById("node-detail")?.classList.add("hidden");
}

function render(snapshot: GraphSnapshot): void {
  const container = document.getElementById("graph-container");
  if (!container) return;
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

async function loadAndRender(): Promise<void> {
  try {
    const snapshot = await graphAPI.getSnapshot();
    render(snapshot);
  } catch (err) {
    // Puo' succedere al primissimo caricamento in background, prima che
    // brain_service sia pronto: non e' un errore fatale, la finestra si
    // riaggiorna comunque ogni volta che viene mostrata (vedi graph-window.ts).
    console.warn("Impossibile caricare il grafo (probabilmente brain_service non e' ancora pronto):", err);
  }
}

function initRefreshButton(): void {
  const button = document.getElementById("refresh-now-button") as HTMLButtonElement | null;
  if (!button) return;
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
    } catch (err) {
      console.error("Aggiornamento manuale del grafo fallito:", err);
    } finally {
      button.disabled = false;
      button.textContent = defaultLabel;
    }
    await refreshDreamTimer();
  });
}

function initMinConnectionsSlider(): void {
  const slider = document.getElementById("min-connections") as HTMLInputElement | null;
  const valueLabel = document.getElementById("min-connections-value");
  if (!slider || !valueLabel) return;

  slider.addEventListener("input", () => {
    minConnectionsFilter = Number(slider.value);
    valueLabel.textContent = slider.value;
    // nodeVisibility e' un accessor riletto ad ogni frame, ma se la
    // simulazione si e' gia' fermata (grafo stabile) non ridisegna da sola:
    // un piccolo reheat forza il ricalcolo visibile subito.
    graph?.d3ReheatSimulation();
  });
}

function initRepulsionSlider(): void {
  const slider = document.getElementById("repulsion") as HTMLInputElement | null;
  if (!slider) return;

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
function initAttractionSlider(): void {
  const slider = document.getElementById("attraction") as HTMLInputElement | null;
  if (!slider) return;

  slider.addEventListener("input", () => {
    const distance = Number(slider.value);
    graph?.d3Force("link")?.distance?.(distance);
    graph?.d3ReheatSimulation();
  });
}

function formatDreamTime(iso: string | null): string {
  if (!iso) return "mai";
  const date = new Date(iso);
  return date.toLocaleString("it-IT", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

async function refreshDreamTimer(): Promise<void> {
  const lastEl = document.getElementById("last-dream-at");
  const nextEl = document.getElementById("next-dream-at");
  if (!lastEl || !nextEl) return;
  try {
    const status = await graphAPI.getDreamingStatus();
    lastEl.textContent = formatDreamTime(status.lastDreamAt);
    nextEl.textContent = formatDreamTime(status.nextScheduledAt);
  } catch (err) {
    console.warn("Impossibile leggere lo stato del dreaming:", err);
  }
}

async function refreshQuantumStatus(): Promise<void> {
  const button = document.getElementById("quantum-button") as HTMLButtonElement | null;
  const statusEl = document.getElementById("quantum-status");
  if (!button || !statusEl) return;
  try {
    const status = await graphAPI.getQuantumStatus();
    button.textContent = status.active ? "Ferma Quantum" : "Modalita' Quantum";
    button.classList.toggle("active", status.active);
    statusEl.classList.toggle("hidden", !status.active);
    if (status.active) {
      statusEl.textContent = `Attiva — iterazione ${status.iterationsDone}. Ascolto e sogni normali sono in pausa.`;
    }
  } catch (err) {
    console.warn("Impossibile leggere lo stato della modalita' Quantum:", err);
  }
}

function initQuantumButton(): void {
  const button = document.getElementById("quantum-button") as HTMLButtonElement | null;
  if (!button) return;

  button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      const current = await graphAPI.getQuantumStatus();
      if (current.active) {
        await graphAPI.stopQuantum();
      } else {
        await graphAPI.startQuantum();
      }
    } catch (err) {
      console.error("Impossibile cambiare stato della modalita' Quantum:", err);
    } finally {
      button.disabled = false;
      await refreshQuantumStatus();
    }
  });
}

function init(): void {
  loadAndRender();
  graphAPI.onUpdated(() => loadAndRender());
  initRefreshButton();
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
