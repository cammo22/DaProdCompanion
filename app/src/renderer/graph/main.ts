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
  x?: number;
  y?: number;
}

declare const graphAPI: {
  getSnapshot(): Promise<GraphSnapshot>;
  onUpdated(callback: () => void): void;
};

declare class ForceGraph {
  constructor(element: HTMLElement);
  graphData(data: { nodes: RenderNode[]; links: { source: string; target: string; edgeType: string }[] }): this;
  nodeId(id: string): this;
  nodeLabel(accessor: (node: RenderNode) => string): this;
  linkColor(accessor: () => string): this;
  nodeCanvasObject(fn: (node: RenderNode, ctx: CanvasRenderingContext2D, scale: number) => void): this;
  nodePointerAreaPaint(
    fn: (node: RenderNode, color: string, ctx: CanvasRenderingContext2D, scale: number) => void,
  ): this;
  onNodeClick(callback: (node: RenderNode) => void): this;
  backgroundColor(color: string): this;
  width(w: number): this;
  height(h: number): this;
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

function toGraphData(snapshot: GraphSnapshot) {
  return {
    nodes: snapshot.nodes.map((n) => ({ id: String(n.id), nodeType: n.node_type, label: n.label })),
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

function init(): void {
  loadAndRender();
  graphAPI.onUpdated(() => loadAndRender());

  document.getElementById("node-detail-close")?.addEventListener("click", () => hideNodeDetail());

  window.addEventListener("resize", () => {
    const container = document.getElementById("graph-container");
    if (container && graph) {
      graph.width(container.clientWidth).height(container.clientHeight);
    }
  });
}

init();
