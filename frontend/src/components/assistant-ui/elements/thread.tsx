import {
  AuiIf,
  ComposerPrimitive,
  MessagePartPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useAui,
  unstable_useComposerInput,
} from "@assistant-ui/react";
import { useScribe } from "@elevenlabs/react";
import { useCallback, useState } from "react";
import { MarkdownTextPrimitive } from "@assistant-ui/react-markdown";
import remarkGfm from "remark-gfm";

type Modality = "text" | "voice";

type ThreadProps = {
  modality: Modality;
  setModality: (value: Modality) => void;
  isProcessing: boolean;
  isSpeaking: boolean;
};

/**
 * The official assistant-ui Thread element is a composed surface: primitives
 * provide the runtime behavior and the element owns the presentation. This
 * Vite app keeps that same boundary, with local CSS tokens instead of a
 * shadcn/Tailwind build step so the FastAPI bundle stays self-contained.
 */
export function Thread({ modality, setModality, isProcessing, isSpeaking }: ThreadProps) {
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
          {isProcessing ? <ThinkingPlaceholder /> : null}

          <ThreadPrimitive.ViewportFooter className="aui-styled-footer">
            <Composer modality={modality} setModality={setModality} isSpeaking={isSpeaking} />
          </ThreadPrimitive.ViewportFooter>
        </div>
      </ThreadPrimitive.Viewport>
    </ThreadPrimitive.Root>
  );
}

function ThinkingPlaceholder() {
  return (
    <div className="aui-styled-message aui-styled-assistant-message aui-thinking-message" role="status" aria-label="Thinking...">
      <div className="aui-styled-avatar aui-assistant-avatar" aria-hidden="true">CC</div>
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

function Composer({ modality, setModality, isSpeaking }: Pick<ThreadProps, "modality" | "setModality" | "isSpeaking">) {
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const [pendingTranscript, setPendingTranscript] = useState<string | null>(null);
  const aui = useAui();
  const { canSend } = unstable_useComposerInput();

  const queueTranscript = useCallback((rawText: string) => {
    const transcript = rawText.trim();
    if (!transcript) return;
    aui.composer.setText(transcript);
    setPendingTranscript(transcript);
  }, [aui]);

  const scribe = useScribe({
    modelId: "scribe_v2_realtime",
    onPartialTranscript: () => setVoiceError(null),
    onCommittedTranscript: ({ text }) => queueTranscript(text),
    onError: (error) => setVoiceError(error instanceof Error ? error.message : "Voice transcription failed."),
  });

  const sendCurrentComposer = useCallback(() => {
    const composer = aui.composer.getState();
    if (!composer.isEditing || composer.isEmpty || !composer.canSend || !canSend) return;
    aui.composer.send();
    setPendingTranscript(null);
  }, [aui, canSend]);

  const toggleVoice = useCallback(async () => {
    setModality("voice");
    setVoiceError(null);
    if (scribe.isConnected) {
      scribe.disconnect();
      return;
    }
    try {
      const response = await fetch("/voice/scribe-token");
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(String(payload.detail ?? `Voice setup failed: ${response.status}`));
      }
      const { token } = (await response.json()) as { token?: string };
      if (!token) throw new Error("Voice setup returned no transcription token.");
      await scribe.connect({
        token,
        microphone: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
    } catch (error) {
      scribe.disconnect();
      setVoiceError(error instanceof Error ? error.message : "Voice transcription failed.");
    }
  }, [scribe, setModality]);

  const voiceStatus = scribe.isConnected
    ? scribe.partialTranscript || "Listening…"
    : isSpeaking
      ? "Advisor is speaking…"
      : pendingTranscript
        ? "Transcript ready — click send"
      : voiceError || "Click the microphone to speak";

  return (
    <ComposerPrimitive.Root className="aui-styled-composer">
      <div className="aui-composer-input-wrap">
        <ComposerPrimitive.Input rows={1} placeholder="Message Classic Car Advisor" />
        <button
          className={`aui-voice-button${scribe.isConnected ? " active" : ""}`}
          type="button"
          onClick={toggleVoice}
          aria-label={scribe.isConnected ? "Stop voice input" : "Start voice input"}
          title={scribe.isConnected ? "Stop voice input" : "Start voice input"}
        >
          <span aria-hidden="true">{scribe.isConnected ? "■" : "●"}</span>
        </button>
        <button
          className="aui-styled-send"
          type="button"
          onClick={sendCurrentComposer}
          disabled={!canSend}
          aria-label="Send message"
          title={pendingTranscript ? "Send transcript to advisor" : "Send message"}
        >
          <span aria-hidden="true">↑</span>
        </button>
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
        <span className={`aui-composer-hint${voiceError ? " voice-error" : ""}`} aria-live="polite">
          {modality === "voice" ? voiceStatus : "Grounded by inventory and source records"}
        </span>
      </div>
    </ComposerPrimitive.Root>
  );
}
