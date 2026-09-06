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

type Preferences = {
  budget_max?: number | null;
  intended_use?: string | null;
  body_style?: string | null;
  driving_style?: string | null;
  selected_vehicle_id?: string | null;
};

type ConversationState = {
  stage?: string;
  preferences?: Preferences;
  last_vehicle_ids?: string[];
};

type ToolCall = {
  name: string;
  arguments: Record<string, unknown>;
  result: unknown;
};

type Review = {
  id: string;
  outlet: string;
  title: string;
  url: string;
  summary: string;
};

type ReviewGroup = {
  vehicle_id: string;
  vehicle_name: string;
  reviews: Review[];
};

type ChatPayload = {
  message: string;
  state: ConversationState;
  trace: ToolCall[];
  reviews: ReviewGroup[];
};

type TraceStreamEvent = {
  trace_id: string;
  status: "running" | "complete";
  name: string;
  arguments: Record<string, unknown>;
  call?: ToolCall;
};

type ActiveTrace = Omit<TraceStreamEvent, "status" | "call"> & { status: "running" };

type Dashboard = {
  state: ConversationState;
  trace: ToolCall[];
  reviews: ReviewGroup[];
  activeTrace: ActiveTrace[];
  turnTraceCount: number;
  isProcessing: boolean;
};

const EMPTY_DASHBOARD: Dashboard = {
  state: { stage: "qualifying", preferences: {}, last_vehicle_ids: [] },
  trace: [],
  reviews: [],
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
              <summary>{index + 1}. {call.name}</summary>
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
        state: payload.state,
        trace: mergeTraceHistory(current.trace, current.turnTraceCount, payload.trace),
        reviews: payload.reviews,
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
