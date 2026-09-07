import {
  AuiIf,
  ComposerPrimitive,
  MessagePartPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useAui,
  unstable_useComposerInput,
} from "@assistant-ui/react";
import { useCallback } from "react";
import { MarkdownTextPrimitive } from "@assistant-ui/react-markdown";
import remarkGfm from "remark-gfm";

type ThreadProps = {
  isProcessing: boolean;
};

/**
 * The official assistant-ui Thread element is a composed surface: primitives
 * provide the runtime behavior and the element owns the presentation. This
 * Vite app keeps that same boundary, with local CSS tokens instead of a
 * shadcn/Tailwind build step so the FastAPI bundle stays self-contained.
 */
export function Thread({ isProcessing }: ThreadProps) {
  return (
    <ThreadPrimitive.Root className="aui-styled-thread">
      <ThreadPrimitive.Viewport className="aui-styled-viewport">
        <div className="aui-thread-content">
          <AuiIf condition={(state) => state.thread.isEmpty}>
            <div className="aui-thread-welcome">
              <div className="aui-welcome-mark" aria-hidden="true">GP</div>
            </div>
          </AuiIf>

          <ThreadPrimitive.Messages>
            {({ message }) => (message.role === "user" ? <UserMessage /> : <AssistantMessage />)}
          </ThreadPrimitive.Messages>
          {isProcessing ? <ThinkingPlaceholder /> : null}

          <ThreadPrimitive.ViewportFooter className="aui-styled-footer">
            <Composer />
          </ThreadPrimitive.ViewportFooter>
        </div>
      </ThreadPrimitive.Viewport>
    </ThreadPrimitive.Root>
  );
}

function ThinkingPlaceholder() {
  return (
    <div className="aui-styled-message aui-styled-assistant-message aui-thinking-message" role="status" aria-label="Thinking...">
      <div className="aui-styled-avatar aui-assistant-avatar" aria-hidden="true">GP</div>
      <div className="aui-styled-message-body">
        <div className="aui-styled-message-label">Advisor</div>
        <div className="aui-thinking-indicator">
          <span>Thinking</span>
          <span className="aui-thinking-dots" aria-hidden="true">
            <span>.</span>
            <span>.</span>
            <span>.</span>
          </span>
        </div>
      </div>
    </div>
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
      <div className="aui-styled-avatar aui-assistant-avatar" aria-hidden="true">GP</div>
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

function Composer() {
  const aui = useAui();
  const { canSend } = unstable_useComposerInput();

  const sendCurrentComposer = useCallback(() => {
    const composer = aui.composer.getState();
    if (!composer.isEditing || composer.isEmpty || !composer.canSend || !canSend) return;
    aui.composer.send();
  }, [aui, canSend]);

  return (
    <ComposerPrimitive.Root className="aui-styled-composer">
      <div className="aui-composer-input-wrap">
        <ComposerPrimitive.Input rows={1} placeholder="Message Grand Prix Motors" />
        <button
          className="aui-styled-send"
          type="button"
          onClick={sendCurrentComposer}
          disabled={!canSend}
          aria-label="Send message"
          title="Send message"
        >
          <span aria-hidden="true">↑</span>
        </button>
      </div>
    </ComposerPrimitive.Root>
  );
}
