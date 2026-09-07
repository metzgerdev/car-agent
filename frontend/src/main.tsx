import {
  AssistantRuntimeProvider,
  useLocalRuntime,
  type ChatModelAdapter,
  type ThreadMessage,
} from "@assistant-ui/react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { Thread } from "./components/assistant-ui/elements/thread";
import { mergeTraceHistory } from "./trace-history.js";
import "./styles.css";

type ToolCall = {
  name: string;
  arguments: Record<string, unknown>;
  result: unknown;
  phase: "retrieve" | "evaluate" | "act";
  purpose: string;
  outcome: string;
  duration_ms: number;
};

type ChatPayload = {
  message: string;
  trace: ToolCall[];
};

type InventoryVehicle = {
  id: string;
  name: string;
  make: string;
  model: string;
  year: number;
  price: number;
  mileage: number;
  body_style: string;
  transmission: string;
  drivetrain: string;
  horsepower: number;
  description: string;
  tags: string[];
};

type InventoryPayload = {
  total: number;
  vehicles: InventoryVehicle[];
};

type TraceStreamEvent = {
  trace_id: string;
  status: "running" | "complete";
  name: string;
  phase: "retrieve" | "evaluate" | "act";
  purpose: string;
  outcome: string;
  duration_ms: number | null;
  arguments: Record<string, unknown>;
  call?: ToolCall;
};

type ActiveTrace = Omit<TraceStreamEvent, "status" | "call"> & { status: "running" };

type Dashboard = {
  trace: ToolCall[];
  activeTrace: ActiveTrace[];
  turnTraceCount: number;
  isProcessing: boolean;
};

const EMPTY_DASHBOARD: Dashboard = {
  trace: [],
  activeTrace: [],
  turnTraceCount: 0,
  isProcessing: false,
};

function newConversationId() {
  if (window.crypto && typeof window.crypto.randomUUID === "function") {
    return `ui-${window.crypto.randomUUID()}`;
  }
  return `ui-${Date.now()}`;
}

function latestUserText(messages: readonly ThreadMessage[]) {
  const message = [...messages].reverse().find((candidate) => candidate.role === "user");
  if (!message) return "";
  return message.content
    .filter((part): part is { type: "text"; text: string } => part.type === "text")
    .map((part) => part.text)
    .join("\n")
    .trim();
}

function createChatAdapter(
  conversationId: string,
  onStreamStarted: () => void,
  onResponseDelta: () => void,
  onResponse: (payload: ChatPayload) => void,
  onTrace: (event: TraceStreamEvent) => void,
  onStreamFinished: () => void,
): ChatModelAdapter {
  return {
    async *run({ messages, abortSignal }) {
      try {
        onStreamStarted();
        const message = latestUserText(messages);
        const response = await fetch("/chat", {
          method: "POST",
          headers: {
            Accept: "text/event-stream",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ conversation_id: conversationId, message }),
          signal: abortSignal,
        });
        if (!response.ok) {
          throw new Error(`Advisor API error: ${response.status} ${response.statusText}`);
        }
        if (!response.body) {
          throw new Error("Advisor API did not return a streaming response.");
        }

        let payload: ChatPayload | null = null;
        let streamedMessage = "";
        for await (const [eventName, data] of consumeSse(response)) {
          if (eventName === "trace") {
            onTrace(data as TraceStreamEvent);
          } else if (eventName === "response_delta") {
            const delta = (data as { delta?: unknown }).delta;
            if (typeof delta === "string" && delta) {
              onResponseDelta();
              streamedMessage += delta;
              yield { content: [{ type: "text", text: streamedMessage }] };
            }
          } else if (eventName === "response") {
            payload = data as ChatPayload;
            onResponse(payload);
          } else if (eventName === "error") {
            throw new Error(String((data as { message?: string }).message ?? "Advisor request failed."));
          } else if (eventName === "done") {
            onStreamFinished();
          }
        }
        if (payload === null) {
          throw new Error("Advisor stream ended without a response.");
        }
        const finalPayload = payload as ChatPayload;
        yield {
          content: [{ type: "text", text: finalPayload.message }],
          status: { type: "complete", reason: "stop" },
        };
      } finally {
        onStreamFinished();
      }
    },
  };
}

function parseSseBlock(block: string): [string, unknown] | null {
  let eventName = "message";
  const dataLines: string[] = [];
  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith("event:")) eventName = line.slice(6).trim();
    if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  if (!dataLines.length) return null;
  return [eventName, JSON.parse(dataLines.join("\n"))];
}

async function* consumeSse(response: Response): AsyncGenerator<[string, unknown]> {
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finished = false;

  while (!finished) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      const event = parseSseBlock(block);
      if (event) yield event;
    }
    finished = done;
  }
  if (buffer.trim()) {
    const event = parseSseBlock(buffer);
    if (event) yield event;
  }
}

function vehicleLabel(value: unknown): string {
  if (typeof value !== "string" || !value) return "the vehicle";
  const match = value.match(/^(.*)-(\d{4})$/);
  const identity = match ? `${match[2]} ${match[1]}` : value;
  return identity.replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function traceProgressLabel(event: ActiveTrace): string {
  const args = event.arguments;
  const filters = args.filters as Record<string, unknown> | undefined;
  const query = typeof filters?.query === "string" ? ` for “${filters.query}”` : "";
  const vehicle = vehicleLabel(args.vehicle_id);
  switch (event.name) {
    case "search_inventory": return `Searching inventory${query}…`;
    case "lookup_vehicle_exact": return `Checking exact availability for ${args.year ?? "the requested"} ${args.make ?? "vehicle"} ${args.model ?? ""}…`;
    case "get_vehicle": return `Loading listing details for ${vehicle}…`;
    case "retrieve_vehicle_facts": return `Retrieving sourced facts for ${vehicle}…`;
    case "retrieve_service_history": return `Retrieving service history for ${vehicle}…`;
    case "retrieve_magazine_reviews": return `Retrieving magazine reviews for ${vehicle}…`;
    case "compare_vehicles": return "Comparing the grounded vehicle options…";
    case "schedule_test_drive": return `Validating the test-drive request for ${vehicle}…`;
    default: return `Running ${event.name}…`;
  }
}

function tracePhaseLabel(phase: ToolCall["phase"]): string {
  return phase === "retrieve" ? "Retrieve" : phase === "evaluate" ? "Evaluate" : "Act";
}

function traceToolLabel(name: string): string {
  return name
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function formatDuration(durationMs: number | null | undefined): string {
  if (typeof durationMs !== "number") return "—";
  return durationMs < 1 ? "<1 ms" : `${Math.round(durationMs)} ms`;
}

function formatPrice(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

const galleryTones = ["copper", "teal", "violet", "gold", "blue", "rose"];
const galleryShots = ["Front three-quarter", "Driver-side profile", "Documentation bay"];

function ListingVisual({
  vehicle,
  shot = 0,
  large = false,
}: {
  vehicle: InventoryVehicle;
  shot?: number;
  large?: boolean;
}) {
  const tone = galleryTones[(vehicle.year + shot) % galleryTones.length];
  return (
    <div
      className={`listing-visual tone-${tone}${large ? " listing-visual-large" : ""}`}
      role="img"
      aria-label={`${galleryShots[shot % galleryShots.length]} synthetic gallery image for ${vehicle.name}`}
    >
      <div className="visual-skyline" />
      <div className="visual-sun" />
      <div className="visual-car">
        <div className="visual-window" />
        <span className="visual-wheel visual-wheel-front" />
        <span className="visual-wheel visual-wheel-rear" />
      </div>
      <div className="visual-topline">
        <span>CLASSIC CAR ADVISOR</span>
        <span>LOT {vehicle.id.slice(-4).toUpperCase()}</span>
      </div>
      <div className="visual-bottomline">
        <strong>{vehicle.year} {vehicle.make}</strong>
        <span>{galleryShots[shot % galleryShots.length]}</span>
      </div>
      <span className="visual-synthetic">SYNTHETIC PHOTO</span>
    </div>
  );
}

function InventoryGallery() {
  const [inventory, setInventory] = useState<InventoryVehicle[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState("");
  const [selectedVehicle, setSelectedVehicle] = useState<InventoryVehicle | null>(null);
  const [activeShot, setActiveShot] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    fetch("/inventory?limit=12")
      .then((response) => {
        if (!response.ok) throw new Error("inventory request failed");
        return response.json() as Promise<InventoryPayload>;
      })
      .then((payload) => {
        if (!active) return;
        setInventory(payload.vehicles);
        setTotal(payload.total);
      })
      .catch(() => {
        if (active) setError(true);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedVehicle) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSelectedVehicle(null);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedVehicle]);

  const normalizedQuery = query.trim().toLowerCase();
  const visibleVehicles = inventory.filter((vehicle) => {
    if (!normalizedQuery) return true;
    return `${vehicle.name} ${vehicle.body_style} ${vehicle.tags.join(" ")}`
      .toLowerCase()
      .includes(normalizedQuery);
  });

  const selectVehicle = (vehicle: InventoryVehicle) => {
    setSelectedVehicle(vehicle);
    setActiveShot(0);
  };

  return (
    <>
      <section className="inventory-gallery panel" aria-label="Featured inventory gallery">
        <div className="gallery-heading">
          <div>
            <p className="eyebrow">Featured inventory</p>
            <h2>Enthusiast cars worth a closer look</h2>
            <p className="gallery-subtitle">
              {total ? `${total.toLocaleString()} synthetic listings` : "Loading synthetic listings"} · auction-style presentation
            </p>
          </div>
          <label className="gallery-search">
            <span className="sr-only">Filter featured inventory</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Filter make, model, or tag"
              type="search"
            />
          </label>
        </div>
        {loading ? <p className="gallery-state">Loading featured inventory…</p> : null}
        {error ? <p className="gallery-state gallery-error">Featured inventory is unavailable. The chat remains available.</p> : null}
        {!loading && !error && !visibleVehicles.length ? <p className="gallery-state">No featured listings match that filter.</p> : null}
        <div className="gallery-grid">
          {visibleVehicles.slice(0, 6).map((vehicle, index) => (
            <article className="inventory-card" key={vehicle.id}>
              <button className="inventory-card-hit" type="button" onClick={() => selectVehicle(vehicle)}>
                <ListingVisual vehicle={vehicle} shot={index % 2} />
                <div className="inventory-card-body">
                  <div className="inventory-card-kicker">
                    <span>{vehicle.body_style}</span>
                    <span>{vehicle.transmission}</span>
                  </div>
                  <h3>{vehicle.name}</h3>
                  <div className="inventory-card-price">
                    <strong>{formatPrice(vehicle.price)}</strong>
                    <span>{vehicle.mileage.toLocaleString()} mi</span>
                  </div>
                  <div className="inventory-tags">
                    {vehicle.tags.slice(0, 3).map((tag) => <span key={tag}>{tag}</span>)}
                  </div>
                </div>
              </button>
            </article>
          ))}
        </div>
        <p className="gallery-footnote">Synthetic gallery visuals · listing details come from the typed mock inventory.</p>
      </section>

      {selectedVehicle ? (
        <div
          className="gallery-modal-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setSelectedVehicle(null);
          }}
        >
          <div className="gallery-modal" role="dialog" aria-modal="true" aria-labelledby="gallery-modal-title">
            <div className="gallery-modal-header">
              <div>
                <p className="eyebrow">Listing preview</p>
                <h2 id="gallery-modal-title">{selectedVehicle.name}</h2>
              </div>
              <button className="gallery-close" type="button" onClick={() => setSelectedVehicle(null)} aria-label="Close listing preview">×</button>
            </div>
            <div className="gallery-modal-layout">
              <div className="gallery-modal-photos">
                <ListingVisual vehicle={selectedVehicle} shot={activeShot} large />
                <div className="gallery-thumbnails" aria-label="Listing photos">
                  {galleryShots.map((shot, index) => (
                    <button
                      className={`gallery-thumbnail${index === activeShot ? " active" : ""}`}
                      type="button"
                      key={shot}
                      onClick={() => setActiveShot(index)}
                      aria-label={`Show ${shot.toLowerCase()} image`}
                    >
                      <ListingVisual vehicle={selectedVehicle} shot={index} />
                    </button>
                  ))}
                </div>
              </div>
              <div className="gallery-modal-details">
                <div className="modal-price-row">
                  <strong>{formatPrice(selectedVehicle.price)}</strong>
                  <span>{selectedVehicle.mileage.toLocaleString()} miles</span>
                </div>
                <p>{selectedVehicle.description}</p>
                <dl className="listing-specs">
                  <div><dt>Power</dt><dd>{selectedVehicle.horsepower} hp</dd></div>
                  <div><dt>Drive</dt><dd>{selectedVehicle.drivetrain}</dd></div>
                  <div><dt>Body</dt><dd>{selectedVehicle.body_style}</dd></div>
                  <div><dt>Transmission</dt><dd>{selectedVehicle.transmission}</dd></div>
                </dl>
                <button className="button button-secondary gallery-modal-action" type="button" onClick={() => setSelectedVehicle(null)}>
                  Close listing preview
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}

function ToolTracePanel({ dashboard }: { dashboard: Dashboard }) {
  return (
    <section className="panel evidence-card tool-trace-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Live agent activity</p>
          <h2>Tool Trace</h2>
        </div>
        <span className="step-count">{dashboard.trace.length + dashboard.activeTrace.length} calls</span>
      </div>
      {dashboard.activeTrace.length ? (
        <div className="trace-progress" aria-live="polite">
          {dashboard.activeTrace.map((event) => (
            <div key={event.trace_id} className="trace-live">
              <span className="trace-spinner" aria-hidden="true" />
              <span>{traceProgressLabel(event)}</span>
            </div>
          ))}
        </div>
      ) : null}
      {dashboard.trace.length ? (
        <div className="trace-list">
          {dashboard.trace.map((call, index) => (
            <details key={`${call.name}-${index}`} className="trace-item">
              <summary>
                <span className="trace-summary-main">
                  <span className={`trace-phase trace-phase-${call.phase}`}>{tracePhaseLabel(call.phase)}</span>
                  <span>{index + 1}. {traceToolLabel(call.name)}</span>
                </span>
                <span className="trace-duration">{formatDuration(call.duration_ms)}</span>
              </summary>
              <div className="trace-explanation">
                <p className="trace-purpose">{call.purpose}</p>
                <p className="trace-outcome"><strong>Outcome:</strong> {call.outcome}</p>
              </div>
              <pre>{JSON.stringify({ arguments: call.arguments, result: call.result }, null, 2)}</pre>
            </details>
          ))}
        </div>
      ) : !dashboard.activeTrace.length ? (
        <p className="empty-state">Tool calls will appear here after the advisor searches inventory or retrieves facts.</p>
      ) : null}
    </section>
  );
}

function AdvisorWorkspace({
  dashboard,
  onReset,
  connectionStatus,
}: {
  dashboard: Dashboard;
  onReset: () => void;
  connectionStatus: "checking" | "connected" | "offline";
}) {
  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">AI engineering demo</p>
          <h1>Classic Car Advisor</h1>
          <p className="subtitle">Find a car, inspect the evidence, and request a test drive.</p>
        </div>
        <div className="topbar-actions">
          <span className={`status-pill ${connectionStatus}`}>{connectionStatus === "checking" ? "Checking API…" : connectionStatus === "connected" ? "API connected" : "API unavailable"}</span>
          <button className="button button-secondary" type="button" onClick={onReset}>New conversation</button>
        </div>
      </header>
      <section className="demo-banner" aria-label="Demo instructions">
        <div>
          <strong>Try the guided flow</strong>
          <span>Start with the Porsche prompt, then add preferences, ask about maintenance, and schedule a drive.</span>
        </div>
        <button className="text-button" type="button" onClick={onReset}>Start over</button>
      </section>
      <InventoryGallery />
      <div className="workspace">
        <section className="conversation-card panel" aria-label="Conversation">
        <Thread isProcessing={dashboard.isProcessing} />
        </section>
        <aside className="sidebar" aria-label="Agent evidence">
          <ToolTracePanel dashboard={dashboard} />
        </aside>
      </div>
    </main>
  );
}

function RuntimeShell({
  conversationId,
  onStreamStarted,
  onResponseDelta,
  onResponse,
  dashboard,
  onReset,
  connectionStatus,
  onTrace,
  onStreamFinished,
}: {
  conversationId: string;
  onStreamStarted: () => void;
  onResponseDelta: () => void;
  onResponse: (payload: ChatPayload) => void;
  onTrace: (event: TraceStreamEvent) => void;
  onStreamFinished: () => void;
  dashboard: Dashboard;
  onReset: () => void;
  connectionStatus: "checking" | "connected" | "offline";
}) {
  const adapter = useMemo(
    () => createChatAdapter(conversationId, onStreamStarted, onResponseDelta, onResponse, onTrace, onStreamFinished),
    [conversationId, onStreamStarted, onResponseDelta, onResponse, onTrace, onStreamFinished],
  );
  const runtime = useLocalRuntime(adapter);
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <AdvisorWorkspace
        dashboard={dashboard}
        onReset={onReset}
        connectionStatus={connectionStatus}
      />
    </AssistantRuntimeProvider>
  );
}

function App() {
  const [conversationId, setConversationId] = useState(newConversationId);
  const [dashboard, setDashboard] = useState<Dashboard>(EMPTY_DASHBOARD);
  const [connectionStatus, setConnectionStatus] = useState<"checking" | "connected" | "offline">("checking");

  useEffect(() => {
    fetch("/health")
      .then((response) => {
        if (!response.ok) throw new Error("health check failed");
        setConnectionStatus("connected");
      })
      .catch(() => setConnectionStatus("offline"));
  }, []);

  const reset = () => {
    setConversationId(newConversationId());
    setDashboard(EMPTY_DASHBOARD);
  };
  const handleStreamStarted = useCallback(() => {
    setDashboard((current) => ({ ...current, activeTrace: [], turnTraceCount: 0, isProcessing: true }));
  }, []);
  const handleResponseDelta = useCallback(() => {
    setDashboard((current) => current.isProcessing ? { ...current, isProcessing: false } : current);
  }, []);
  const handleResponse = useCallback(
    (payload: ChatPayload) => setDashboard((current) => {
      return {
        trace: mergeTraceHistory(current.trace, current.turnTraceCount, payload.trace),
        activeTrace: [],
        turnTraceCount: 0,
        isProcessing: false,
      };
    }),
    [],
  );
  const handleTrace = useCallback((event: TraceStreamEvent) => {
    setDashboard((current) => {
      if (event.status === "running") {
        return {
          ...current,
          activeTrace: [...current.activeTrace, { ...event, status: "running" }],
        };
      }
      return {
        ...current,
        activeTrace: current.activeTrace.filter((active, index) => {
          if (active.trace_id === event.trace_id) return false;
          if (active.name === event.name && !current.activeTrace.some((candidate) => candidate.trace_id === event.trace_id)) {
            return index !== current.activeTrace.findIndex((candidate) => candidate.name === event.name);
          }
          return true;
        }),
        trace: event.call ? [...current.trace, event.call] : current.trace,
        turnTraceCount: event.call ? current.turnTraceCount + 1 : current.turnTraceCount,
      };
    });
  }, []);
  const handleStreamFinished = useCallback(() => {
    setDashboard((current) => {
      if (!current.activeTrace.length && !current.isProcessing) return current;
      return { ...current, activeTrace: [], isProcessing: false };
    });
  }, []);

  return (
    <RuntimeShell
      key={conversationId}
      conversationId={conversationId}
      onStreamStarted={handleStreamStarted}
      onResponseDelta={handleResponseDelta}
      onResponse={handleResponse}
      onTrace={handleTrace}
      onStreamFinished={handleStreamFinished}
      dashboard={dashboard}
      onReset={reset}
      connectionStatus={connectionStatus}
    />
  );
}

createRoot(document.getElementById("root")!).render(<App />);
