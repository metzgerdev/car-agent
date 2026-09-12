import {
  AuiIf,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useAui,
  unstable_useComposerInput,
} from "@assistant-ui/react";
import { useCallback, type ComponentPropsWithoutRef } from "react";
import { MarkdownTextPrimitive } from "@assistant-ui/react-markdown";
import remarkGfm from "remark-gfm";
import { Conversation, ConversationContent } from "../../elevenlabs-ui/conversation";
import { ConversationEmptyState } from "../../elevenlabs-ui/conversation-empty-state";
import { Matrix, type Frame } from "../../elevenlabs-ui/matrix";
import { Message, MessageContent } from "../../elevenlabs-ui/message";
import { ShimmeringText } from "../../elevenlabs-ui/shimmering-text";

function SourceLink({ href, children, ...props }: ComponentPropsWithoutRef<"a">) {
  return <a {...props} href={href} target="_blank" rel="noreferrer">{href}</a>;
}

const markdownComponents = { a: SourceLink };

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
        <Conversation className="elevenlabs-conversation min-h-full flex-none overflow-visible">
          <ConversationContent className="aui-thread-content p-0">
            <AuiIf condition={(state) => state.thread.isEmpty}>
              <ConversationEmptyState
                className="aui-thread-welcome elevenlabs-empty-state"
                icon={<div className="aui-welcome-mark" aria-hidden="true">GP</div>}
                title="Grand Prix Motors"
                description="Specializing in classic/modern-classic enthusiast sports cars"
              >
                <StarterPrompts />
              </ConversationEmptyState>
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
          </ConversationContent>
        </Conversation>
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
    <Message from="assistant" className="elevenlabs-message" role="status" aria-label="Thinking...">
      <MessageContent variant="flat" className="elevenlabs-message-content">
        <div className="elevenlabs-message-label">Advisor</div>
        <div className="aui-thinking-indicator">
          <ShimmeringText text="Grounding your response…" duration={1.6} repeatDelay={0.35} startOnView={false} />
        </div>
      </MessageContent>
      <AdvisorAvatar />
    </Message>
  );
}

function UserMessage() {
  return (
    <MessagePrimitive.Root>
      <Message from="user" className="elevenlabs-message">
        <MessageContent variant="flat" className="elevenlabs-message-content">
          <div className="elevenlabs-message-text aui-styled-markdown">
            <MessagePrimitive.Parts>
              {({ part }) => (part.type === "text" ? <MarkdownTextPrimitive remarkPlugins={[remarkGfm]} components={markdownComponents} /> : null)}
            </MessagePrimitive.Parts>
          </div>
        </MessageContent>
        <div className="elevenlabs-message-avatar elevenlabs-user-avatar" aria-hidden="true">You</div>
      </Message>
    </MessagePrimitive.Root>
  );
}

function AssistantMessage() {
  return (
    <MessagePrimitive.Root>
      <Message from="assistant" className="elevenlabs-message">
        <MessageContent variant="flat" className="elevenlabs-message-content">
          <div className="elevenlabs-message-label">Advisor</div>
          <div className="elevenlabs-message-text aui-styled-markdown">
            <MessagePrimitive.Parts>
              {({ part }) => {
                if (part.type === "text") {
                  return <MarkdownTextPrimitive remarkPlugins={[remarkGfm]} components={markdownComponents} />;
                }
                if (part.type === "tool-call") {
                  return part.toolUI ?? <span className="aui-tool-note">Checking grounded evidence…</span>;
                }
                return null;
              }}
            </MessagePrimitive.Parts>
            <MessagePrimitive.Error />
          </div>
        </MessageContent>
        <AdvisorAvatar />
      </Message>
    </MessagePrimitive.Root>
  );
}

const gpMark: Frame = [
  [0, 1, 1, 0, 0, 1, 1, 1, 0],
  [1, 0, 0, 1, 0, 1, 0, 0, 1],
  [1, 0, 0, 0, 0, 1, 0, 0, 1],
  [1, 0, 1, 1, 0, 1, 1, 1, 0],
  [1, 0, 0, 1, 0, 1, 0, 0, 0],
  [1, 0, 0, 1, 0, 1, 0, 0, 0],
  [0, 1, 1, 0, 0, 1, 0, 0, 0],
];
const gpMarkFrames = [gpMark, gpMark.map((row) => row.map((pixel) => pixel * 0.72))];

function AdvisorAvatar() {
  return (
    <div className="elevenlabs-message-avatar elevenlabs-assistant-avatar" aria-hidden="true">
      <Matrix
        className="gp-matrix"
        rows={7}
        cols={9}
        frames={gpMarkFrames}
        fps={1.4}
        size={2.15}
        gap={0.45}
        palette={{ on: "#ffffff", off: "#52525b" }}
        ariaLabel="Grand Prix Motors"
      />
    </div>
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
