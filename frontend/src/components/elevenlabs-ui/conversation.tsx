import type { ComponentProps } from "react";
import { StickToBottom } from "use-stick-to-bottom";
import { cn } from "../../lib/utils";

/**
 * Adapted from ElevenLabs UI's Conversation and ConversationContent components (MIT).
 * https://ui.elevenlabs.io/docs/components/conversation
 */
export type ConversationProps = ComponentProps<typeof StickToBottom>;

export function Conversation({ className, ...props }: ConversationProps) {
  return (
    <StickToBottom
      className={cn("relative flex-1 overflow-y-auto", className)}
      initial="smooth"
      resize="smooth"
      role="log"
      {...props}
    />
  );
}

export type ConversationContentProps = ComponentProps<typeof StickToBottom.Content>;

export function ConversationContent({ className, ...props }: ConversationContentProps) {
  return <StickToBottom.Content className={cn("p-4", className)} {...props} />;
}
