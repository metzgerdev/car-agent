import {
  forwardRef,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type HTMLAttributes,
} from "react";
import { cn } from "../../lib/utils";

/**
 * Adapted from ElevenLabs UI's Matrix component (MIT).
 * https://ui.elevenlabs.io/docs/components/matrix
 */
export type Frame = number[][];

export type MatrixProps = HTMLAttributes<HTMLDivElement> & {
  rows: number;
  cols: number;
  pattern?: Frame;
  frames?: Frame[];
  fps?: number;
  autoplay?: boolean;
  loop?: boolean;
  size?: number;
  gap?: number;
  palette?: { on: string; off: string };
  brightness?: number;
  ariaLabel?: string;
};

function clamp(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function normalizeFrame(frame: Frame | undefined, rows: number, cols: number): Frame {
  return Array.from({ length: rows }, (_, row) => (
    Array.from({ length: cols }, (_, col) => frame?.[row]?.[col] ?? 0)
  ));
}

export const Matrix = forwardRef<HTMLDivElement, MatrixProps>(function Matrix(
  {
    rows,
    cols,
    pattern,
    frames,
    fps = 12,
    autoplay = true,
    loop = true,
    size = 10,
    gap = 2,
    palette = { on: "currentColor", off: "var(--chat-subtle)" },
    brightness = 1,
    ariaLabel = "matrix display",
    className,
    style,
    ...props
  },
  ref,
) {
  const [frameIndex, setFrameIndex] = useState(0);
  const animationFrame = useRef<number | null>(null);
  const lastUpdate = useRef(0);
  const instanceId = useId().replaceAll(":", "");
  const canAnimate = autoplay && !pattern && Boolean(frames?.length);

  useEffect(() => {
    setFrameIndex(0);
    lastUpdate.current = 0;
  }, [frames, pattern]);

  useEffect(() => {
    if (!canAnimate || !frames?.length) return undefined;

    const interval = 1000 / Math.max(1, fps);
    const animate = (time: number) => {
      if (!lastUpdate.current) lastUpdate.current = time;
      if (time - lastUpdate.current >= interval) {
        lastUpdate.current = time;
        setFrameIndex((current) => (current + 1 < frames.length ? current + 1 : loop ? 0 : current));
      }
      animationFrame.current = requestAnimationFrame(animate);
    };

    animationFrame.current = requestAnimationFrame(animate);
    return () => {
      if (animationFrame.current !== null) cancelAnimationFrame(animationFrame.current);
    };
  }, [canAnimate, fps, frames, loop]);

  const frame = useMemo(
    () => normalizeFrame(pattern ?? frames?.[frameIndex] ?? frames?.[0], rows, cols),
    [cols, frameIndex, frames, pattern, rows],
  );
  const width = cols * (size + gap) - gap;
  const height = rows * (size + gap) - gap;
  const onGradientId = `${instanceId}-matrix-on`;
  const offGradientId = `${instanceId}-matrix-off`;
  const glowId = `${instanceId}-matrix-glow`;

  return (
    <div
      ref={ref}
      role="img"
      aria-label={ariaLabel}
      aria-live={canAnimate ? "polite" : undefined}
      className={cn("elevenlabs-matrix", className)}
      style={{
        ...style,
        "--matrix-on": palette.on,
        "--matrix-off": palette.off,
      } as CSSProperties}
      {...props}
    >
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
        <defs>
          <radialGradient id={onGradientId} cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="var(--matrix-on)" />
            <stop offset="100%" stopColor="var(--matrix-on)" stopOpacity="0.6" />
          </radialGradient>
          <radialGradient id={offGradientId} cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="var(--matrix-off)" />
            <stop offset="100%" stopColor="var(--matrix-off)" stopOpacity="0.5" />
          </radialGradient>
          <filter id={glowId} x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="1" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>
        {frame.flatMap((row, rowIndex) => row.map((value, colIndex) => {
          const opacity = clamp(value * brightness);
          const active = opacity > 0.5;
          const centerX = colIndex * (size + gap) + size / 2;
          const centerY = rowIndex * (size + gap) + size / 2;
          return (
            <circle
              key={`${rowIndex}-${colIndex}`}
              cx={centerX}
              cy={centerY}
              r={(size / 2) * 0.88}
              fill={`url(#${opacity > 0.05 ? onGradientId : offGradientId})`}
              opacity={opacity > 0.05 ? opacity : 0.18}
              filter={active ? `url(#${glowId})` : undefined}
              style={{ transition: "opacity 300ms ease-out, transform 150ms ease-out" }}
            />
          );
        }))}
      </svg>
    </div>
  );
});

Matrix.displayName = "Matrix";
