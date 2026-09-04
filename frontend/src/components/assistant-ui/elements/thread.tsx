import {
  AuiIf,
  ComposerPrimitive,
  MessagePartPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
} from "@assistant-ui/react";
import { MarkdownTextPrimitive } from "@assistant-ui/react-markdown";
import remarkGfm from "remark-gfm";

type Modality = "text" | "voice";

type ThreadProps = {
  modality: Modality;
  setModality: (value: Modality) => void;
};

/**
 * The official assistant-ui Thread element is a composed surface: primitives
 * provide the runtime behavior and the element owns the presentation. This
 * Vite app keeps that same boundary, with local CSS tokens instead of a
 * shadcn/Tailwind build step so the FastAPI bundle stays self-contained.
 */
export function Thread({ modality, setModality }: ThreadProps) {
  return (
    <ThreadPrimitive.Root className="aui-styled-thread">
      <ThreadPrimitive.Viewport className="aui-styled-viewport">
        <div className="aui-thread-content">
          <AuiIf condition={(state) => state.thread.isEmpty}>
            <div className="aui-thread-welcome">
              <div className="aui-welcome-mark" aria-hidden="true">CC</div>
              <p className="eyebrow">Classic Car Advisor</p>
              <h2>What kind of classic or modern-classic sports car are you looking for?</h2>
              <p className="welcome-note">Describe the car, budget, and driving experience you have in mind.</p>
            </div>
          </AuiIf>

          <ThreadPrimitive.Messages>
            {({ message }) => (message.role === "user" ? <UserMessage /> : <AssistantMessage />)}
          </ThreadPrimitive.Messages>

          <ThreadPrimitive.ViewportFooter className="aui-styled-footer">
            <Composer modality={modality} setModality={setModality} />
          </ThreadPrimitive.ViewportFooter>
        </div>
      </ThreadPrimitive.Viewport>
    </ThreadPrimitive.Root>
  );
}

function UserMessage() {
  return (
    <MessagePrimitive.Root className="aui-styled-message aui-styled-user-message">
      <div className="aui-styled-avatar aui-user-avatar" aria-hidden="true">You</div>
      <div className="aui-styled-message-body">
        <div className="aui-styled-message-label">You</div>
        <div className="aui-styled-message-text">
          <MessagePrimitive.Parts>
            {({ part }) => (part.type === "text" ? <MessagePartPrimitive.Text /> : null)}
          </MessagePrimitive.Parts>
        </div>
      </div>
    </MessagePrimitive.Root>
  );
}

function AssistantMessage() {
  return (
    <MessagePrimitive.Root className="aui-styled-message aui-styled-assistant-message">
      <div className="aui-styled-avatar aui-assistant-avatar" aria-hidden="true">CC</div>
      <div className="aui-styled-message-body">
        <div className="aui-styled-message-label">Advisor</div>
        <div className="aui-styled-message-text aui-styled-markdown">
          <MessagePrimitive.Parts>
            {({ part }) => {
              if (part.type === "text") {
                return <MarkdownTextPrimitive remarkPlugins={[remarkGfm]} />;
              }
              if (part.type === "tool-call") {
                return part.toolUI ?? <span className="aui-tool-note">Checking grounded evidence…</span>;
              }
              return null;
            }}
          </MessagePrimitive.Parts>
          <MessagePrimitive.Error />
        </div>
      </div>
    </MessagePrimitive.Root>
  );
}

function Composer({ modality, setModality }: ThreadProps) {
  return (
    <ComposerPrimitive.Root className="aui-styled-composer">
      <div className="aui-composer-input-wrap">
        <ComposerPrimitive.Input rows={1} placeholder="Message Classic Car Advisor" />
        <ComposerPrimitive.Send className="aui-styled-send" aria-label="Send message" title="Send message">
          <span aria-hidden="true">↑</span>
        </ComposerPrimitive.Send>
      </div>
      <div className="aui-styled-composer-footer">
        <label className="aui-styled-modality">
          <span className="aui-mode-dot" aria-hidden="true" />
          <span>Input mode</span>
          <select value={modality} onChange={(event) => setModality(event.target.value as Modality)}>
            <option value="text">Text</option>
            <option value="voice">Voice transcript</option>
          </select>
        </label>
        <span className="aui-composer-hint">Grounded by inventory and source records</span>
      </div>
    </ComposerPrimitive.Root>
  );
}
