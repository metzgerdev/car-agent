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

/** Render the chat thread. */
export function Thread() {
  return (
    <ThreadPrimitive.Root className="aui-styled-thread">
      <ThreadPrimitive.Viewport
        className="aui-styled-viewport"
        autoScroll
        turnAnchor="bottom"
        scrollToBottomOnRunStart
        scrollToBottomOnInitialize
      >
        <div className="aui-thread-content">
          <AuiIf condition={(state) => state.thread.isEmpty}>
            <div className="aui-thread-welcome">
              <div className="aui-welcome-mark" aria-hidden="true">GP</div>
              <p className="aui-welcome-tagline">Specializing in classic/modern-classic enthusiast sports cars</p>
              <StarterPrompts />
            </div>
          </AuiIf>

          <ThreadPrimitive.Messages>
            {({ message }) => {
              if (message.role === "user") return <UserMessage />;
              if (message.status?.type === "running" && message.parts.length === 0) {
                return <ThinkingPlaceholder />;
              }
              return <AssistantMessage />;
            }}
          </ThreadPrimitive.Messages>
        </div>
      </ThreadPrimitive.Viewport>
      <div className="aui-styled-footer">
        <Composer />
      </div>
    </ThreadPrimitive.Root>
  );
}

function StarterPrompts() {
  const aui = useAui();
  const { setText, isDisabled } = unstable_useComposerInput();
  const prompts = [
    "Find a weekend sports car",
    "Show me classic BMWs",
    "Tell me about the Honda S2000",
    "What ownership notes do you have on the Honda S2000?",
    "What do the magazine reviews say about the Mazda RX-7?",
    "Show me the service history for the BMW Z4 M Coupe",
    "Compare the Honda S2000 and Porsche 911 Carrera",
    "Do you have a 2011 BMW M3 in inventory?",
    "Tell me more about the 1999 Porsche 911 Carrera",
  ];

  const sendPrompt = useCallback((prompt: string) => {
    if (isDisabled) return;
    setText(prompt);
    aui.composer.send();
  }, [aui, isDisabled, setText]);

  return (
    <div className="aui-starter-prompts" aria-label="Starter prompts">
      {prompts.map((prompt) => (
        <button
          key={prompt}
          className="aui-starter-prompt"
          type="button"
          onClick={() => sendPrompt(prompt)}
          disabled={isDisabled}
        >
          {prompt}
        </button>
      ))}
    </div>
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
