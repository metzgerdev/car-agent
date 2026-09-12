import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** The utility helper used by the vendored ElevenLabs UI components. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
