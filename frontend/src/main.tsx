import {
  AuiIf,
  AssistantRuntimeProvider,
  ComposerPrimitive,
  MessagePartPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useAui,
  useLocalRuntime,
  type ChatModelAdapter,
  type ThreadMessage,
} from "@assistant-ui/react";
import { MarkdownTextPrimitive } from "@assistant-ui/react-markdown";
import { useCallback, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import remarkGfm from "remark-gfm";
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

type Dashboard = {
  state: ConversationState;
  trace: ToolCall[];
  reviews: ReviewGroup[];
};

const PROMPTS = [
  ["Start with a make", "I want a weekend sports car under $50k. I like Porsche, but I am not sure which model."],
  ["Add preferences", "I am open to a 911 Carrera or 718 Cayman GTS. I prefer a manual, spirited car for weekend drives."],
  ["Ask for facts", "What should I inspect on the Porsche 911 Carrera?"],
  ["Raise an objection", "The maintenance risk worries me. What is the trade-off?"],
  ["Request a drive", "I would like to schedule a test drive for the Porsche 911 Carrera."],
  ["Complete booking", "My name is Alex Rivera, my email is alex@example.com, and Saturday at 10am works."],
] as const;

const EMPTY_DASHBOARD: Dashboard = {
  state: { stage: "qualifying", preferences: {}, last_vehicle_ids: [] },
  trace: [],
  reviews: [],
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
  modality: "text" | "voice",
  onResponse: (payload: ChatPayload) => void,
): ChatModelAdapter {
  return {
    async run({ messages, abortSignal }) {
      const message = latestUserText(messages);
      const response = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ conversation_id: conversationId, message, modality }),
        signal: abortSignal,
      });
      if (!response.ok) {
        throw new Error(`Advisor API error: ${response.status} ${response.statusText}`);
      }
      const payload = (await response.json()) as ChatPayload;
      onResponse(payload);
      return { content: [{ type: "text", text: payload.message }] };
    },
  };
}

function UserMessage() {
  return (
    <MessagePrimitive.Root className="aui-message aui-user-message">
      <div className="aui-message-label">You</div>
      <div className="aui-message-bubble">
        <MessagePrimitive.Parts>
          {({ part }) => (part.type === "text" ? <MessagePartPrimitive.Text /> : null)}
        </MessagePrimitive.Parts>
      </div>
    </MessagePrimitive.Root>
  );
}

function AssistantMessage() {
  return (
    <MessagePrimitive.Root className="aui-message aui-assistant-message">
      <div className="aui-message-label">Advisor</div>
      <div className="aui-message-bubble">
        <MessagePrimitive.Parts>
          {({ part }) => {
            if (part.type === "text") {
              return <MarkdownTextPrimitive className="aui-markdown" remarkPlugins={[remarkGfm]} />;
            }
            if (part.type === "tool-call") {
              return part.toolUI ?? <span className="aui-tool-note">Checking grounded evidence…</span>;
            }
            return null;
          }}
        </MessagePrimitive.Parts>
        <MessagePrimitive.Error />
      </div>
    </MessagePrimitive.Root>
  );
}

function Thread({ modality, setModality }: { modality: "text" | "voice"; setModality: (value: "text" | "voice") => void }) {
  return (
    <ThreadPrimitive.Root className="aui-thread">
      <ThreadPrimitive.Viewport className="aui-viewport">
        <AuiIf condition={(state) => state.thread.isEmpty}>
          <div className="aui-welcome">
            <p className="eyebrow">Start the conversation</p>
            <h2>What kind of classic or modern-classic sports car are you looking for?</h2>
            <p className="welcome-note">Try a prompt or describe the car you want to drive.</p>
          </div>
        </AuiIf>
        <ThreadPrimitive.Messages>
          {({ message }) => (message.role === "user" ? <UserMessage /> : <AssistantMessage />)}
        </ThreadPrimitive.Messages>
        <ThreadPrimitive.ViewportFooter className="aui-viewport-footer">
          <Composer modality={modality} setModality={setModality} />
        </ThreadPrimitive.ViewportFooter>
      </ThreadPrimitive.Viewport>
    </ThreadPrimitive.Root>
  );
}

function Composer({ modality, setModality }: { modality: "text" | "voice"; setModality: (value: "text" | "voice") => void }) {
  return (
    <ComposerPrimitive.Root className="aui-composer">
      <ComposerPrimitive.Input rows={2} placeholder="Tell me what you want to drive…" />
      <div className="aui-composer-footer">
        <label className="aui-modality">
          <span>Input</span>
          <select value={modality} onChange={(event) => setModality(event.target.value as "text" | "voice")}>
            <option value="text">Text</option>
            <option value="voice">Voice transcript</option>
          </select>
          <span className="aui-hint">Voice uses the same domain command boundary.</span>
        </label>
        <ComposerPrimitive.Send className="aui-send">Send message</ComposerPrimitive.Send>
      </div>
    </ComposerPrimitive.Root>
  );
}

function QuickPrompts() {
  const aui = useAui();
  return (
    <section className="panel quick-start">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Demo prompts</p>
          <h2>Guide the shopper</h2>
        </div>
        <span className="step-count">6 steps</span>
      </div>
      <div className="quick-prompts">
        {PROMPTS.map(([label, prompt], index) => (
          <button key={label} className="prompt-button" type="button" onClick={() => aui.composer.setText(prompt)}>
            {index + 1}. {label}
          </button>
        ))}
      </div>
    </section>
  );
}

function EvidencePanel({ dashboard }: { dashboard: Dashboard }) {
  const preferences = dashboard.state.preferences ?? {};
  const vehicle = preferences.selected_vehicle_id ?? dashboard.state.last_vehicle_ids?.[0];
  const profile = [
    ["Budget", preferences.budget_max ? `$${Number(preferences.budget_max).toLocaleString()} max` : "Not set"],
    ["Use", preferences.intended_use ?? "Not set"],
    ["Style", preferences.driving_style ?? preferences.body_style ?? "Not set"],
    ["Vehicle", vehicle ?? "Not selected"],
  ];

  return (
    <>
      <section className="panel evidence-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Inspectable state</p>
            <h2>Shopper profile</h2>
          </div>
          <span className="stage-badge">{(dashboard.state.stage ?? "qualifying").replaceAll("_", " ")}</span>
        </div>
        <dl className="profile-list">
          {profile.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd title={value}>{value}</dd>
            </div>
          ))}
        </dl>
      </section>
      <ReviewsPanel groups={dashboard.reviews} />
      <section className="panel evidence-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Tool trace</p>
            <h2>Grounding evidence</h2>
          </div>
          <span className="step-count">{dashboard.trace.length} calls</span>
        </div>
        {dashboard.trace.length ? (
          <div className="trace-list">
            {dashboard.trace.map((call, index) => (
              <details key={`${call.name}-${index}`} className="trace-item">
                <summary>{index + 1}. {call.name}</summary>
                <pre>{JSON.stringify({ arguments: call.arguments, result: call.result }, null, 2)}</pre>
              </details>
            ))}
          </div>
        ) : (
          <p className="empty-state">Tool calls will appear here after the advisor searches inventory or retrieves facts.</p>
        )}
      </section>
    </>
  );
}

function ReviewsPanel({ groups }: { groups: ReviewGroup[] }) {
  const [selected, setSelected] = useState<{ vehicleName: string; review: Review } | null>(null);
  const reviewTotal = groups.reduce((total, group) => total + group.reviews.length, 0);
  return (
    <>
      <section className="panel evidence-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Editorial context</p>
            <h2>Magazine reviews</h2>
          </div>
          <span className="step-count">{reviewTotal} review{reviewTotal === 1 ? "" : "s"}</span>
        </div>
        {reviewTotal ? (
          <div className="reviews-list">
            {groups.map((group) => (
              <div key={group.vehicle_id} className="review-group">
                <p className="review-vehicle">{group.vehicle_name}</p>
                {group.reviews.map((review) => (
                  <button key={review.id} className="review-button" type="button" onClick={() => setSelected({ vehicleName: group.vehicle_name, review })}>
                    <span className="review-outlet">{review.outlet}</span>
                    <span className="review-title">{review.title}</span>
                  </button>
                ))}
              </div>
            ))}
          </div>
        ) : (
          <p className="empty-state">Reviews will appear when the advisor finds a vehicle.</p>
        )}
      </section>
      {selected ? (
        <div className="review-overlay" role="presentation" onClick={() => setSelected(null)}>
          <section className="review-dialog" role="dialog" aria-modal="true" aria-labelledby="review-dialog-title" onClick={(event) => event.stopPropagation()}>
            <div className="dialog-heading">
              <div>
                <p className="eyebrow">{selected.review.outlet}</p>
                <h2 id="review-dialog-title">{selected.review.title}</h2>
              </div>
              <button className="dialog-close" type="button" aria-label="Close review" onClick={() => setSelected(null)}>×</button>
            </div>
            <p className="dialog-vehicle">{selected.vehicleName}</p>
            <p className="dialog-summary">{selected.review.summary}</p>
            <a className="button button-primary" href={selected.review.url} target="_blank" rel="noopener noreferrer">Read the full review</a>
          </section>
        </div>
      ) : null}
    </>
  );
}

function AdvisorWorkspace({
  dashboard,
  modality,
  setModality,
  onReset,
  connectionStatus,
}: {
  dashboard: Dashboard;
  modality: "text" | "voice";
  setModality: (value: "text" | "voice") => void;
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
          <Thread modality={modality} setModality={setModality} />
        </section>
        <aside className="sidebar" aria-label="Agent evidence">
          <QuickPrompts />
          <EvidencePanel dashboard={dashboard} />
        </aside>
      </div>
    </main>
  );
}

function RuntimeShell({
  conversationId,
  modality,
  setModality,
  onResponse,
  dashboard,
  onReset,
  connectionStatus,
}: {
  conversationId: string;
  modality: "text" | "voice";
  setModality: (value: "text" | "voice") => void;
  onResponse: (payload: ChatPayload) => void;
  dashboard: Dashboard;
  onReset: () => void;
  connectionStatus: "checking" | "connected" | "offline";
}) {
  const adapter = useMemo(
    () => createChatAdapter(conversationId, modality, onResponse),
    [conversationId, modality, onResponse],
  );
  const runtime = useLocalRuntime(adapter);
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <AdvisorWorkspace
        dashboard={dashboard}
        modality={modality}
        setModality={setModality}
        onReset={onReset}
        connectionStatus={connectionStatus}
      />
    </AssistantRuntimeProvider>
  );
}

function App() {
  const [conversationId, setConversationId] = useState(newConversationId);
  const [modality, setModality] = useState<"text" | "voice">("text");
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
  const handleResponse = useCallback(
    (payload: ChatPayload) => setDashboard({ state: payload.state, trace: payload.trace, reviews: payload.reviews }),
    [],
  );

  return (
    <RuntimeShell
      key={conversationId}
      conversationId={conversationId}
      modality={modality}
      setModality={setModality}
      onResponse={handleResponse}
      dashboard={dashboard}
      onReset={reset}
      connectionStatus={connectionStatus}
    />
  );
}

createRoot(document.getElementById("root")!).render(<App />);
