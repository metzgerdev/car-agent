import type { ComponentProps, ReactNode } from "react";
import { cn } from "../../lib/utils";

/**
 * Adapted from ElevenLabs UI's ConversationEmptyState component (MIT).
 * https://ui.elevenlabs.io/docs/components/conversation
 */
export type ConversationEmptyStateProps = Omit<ComponentProps<"div">, "title"> & {
  title?: ReactNode;
  description?: ReactNode;
  icon?: ReactNode;
};

export function ConversationEmptyState({
  className,
  title = "No messages yet",
  description = "Start a conversation to see messages here",
  icon,
  children,
  ...props
}: ConversationEmptyStateProps) {
  return (
    <div
      className={cn("flex size-full flex-col items-center justify-center gap-3 p-8 text-center", className)}
      {...props}
    >
      {icon ? <div className="text-muted-foreground">{icon}</div> : null}
      <div className="space-y-1">
        <h3 className="text-sm font-medium">{title}</h3>
        {description ? <p className="text-muted-foreground text-sm">{description}</p> : null}
      </div>
      {children}
    </div>
  );
}
