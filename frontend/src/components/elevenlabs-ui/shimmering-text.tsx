import { type CSSProperties, useMemo, useRef } from "react";
import { motion, useInView, type UseInViewOptions } from "motion/react";
import { cn } from "../../lib/utils";

/**
 * Adapted from ElevenLabs UI's ShimmeringText component (MIT).
 * https://ui.elevenlabs.io/docs/components/shimmering-text
 */
export type ShimmeringTextProps = {
  text: string;
  duration?: number;
  delay?: number;
  repeat?: boolean;
  repeatDelay?: number;
  className?: string;
  startOnView?: boolean;
  once?: boolean;
  inViewMargin?: UseInViewOptions["margin"];
  spread?: number;
  color?: string;
  shimmerColor?: string;
};

export function ShimmeringText({
  text,
  duration = 2,
  delay = 0,
  repeat = true,
  repeatDelay = 0.5,
  className,
  startOnView = true,
  once = false,
  inViewMargin,
  spread = 2,
  color,
  shimmerColor,
}: ShimmeringTextProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const isInView = useInView(ref, { once, margin: inViewMargin });
  const dynamicSpread = useMemo(() => text.length * spread, [text, spread]);
  const shouldAnimate = !startOnView || isInView;

  return (
    <motion.span
      ref={ref}
      className={cn(
        "relative inline-block bg-[length:250%_100%,auto] bg-clip-text text-transparent",
        "[background-repeat:no-repeat,padding-box]",
        "[--shimmer-bg:linear-gradient(90deg,transparent_calc(50%-var(--spread)),var(--shimmer-color),transparent_calc(50%+var(--spread)))]",
        className,
      )}
      style={{
        "--spread": `${dynamicSpread}px`,
        "--base-color": color ?? "var(--chat-muted)",
        "--shimmer-color": shimmerColor ?? "var(--chat-text)",
        backgroundImage: "var(--shimmer-bg), linear-gradient(var(--base-color), var(--base-color))",
      } as CSSProperties}
      initial={{ backgroundPosition: "100% center", opacity: 0 }}
      animate={shouldAnimate ? { backgroundPosition: "0% center", opacity: 1 } : {}}
      transition={{
        backgroundPosition: {
          repeat: repeat ? Infinity : 0,
          duration,
          delay,
          repeatDelay,
          ease: "linear",
        },
        opacity: { duration: 0.3, delay },
      }}
    >
      {text}
    </motion.span>
  );
}
