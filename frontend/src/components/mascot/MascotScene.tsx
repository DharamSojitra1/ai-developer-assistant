import type { CSSProperties } from "react";

import { cn } from "@/lib/cn";

import { Mascot, type MascotMood } from "./Mascot";

const MINI_ORBS: { tint: string; size: number; style: CSSProperties; className?: string }[] = [
  {
    tint: "var(--color-bot)",
    size: 20,
    style: { left: "6%", top: "16%", animationDuration: "7s" },
  },
  {
    tint: "var(--color-mascot-cyan)",
    size: 16,
    style: { right: "4%", top: "34%", animationDuration: "8.5s", animationDelay: "-3s" },
    className: "hidden sm:block",
  },
  {
    tint: "var(--color-bot-light)",
    size: 12,
    style: { left: "18%", bottom: "6%", animationDuration: "6s", animationDelay: "-1.5s" },
    className: "hidden sm:block",
  },
];

const SPARKLES: CSSProperties[] = [
  { left: "24%", top: "6%", width: 10, animationDelay: "0s" },
  { right: "20%", top: "10%", width: 8, animationDelay: "-0.8s" },
  { right: "12%", bottom: "16%", width: 9, animationDelay: "-1.6s" },
  { left: "10%", top: "52%", width: 7, animationDelay: "-2.2s" },
  { left: "40%", bottom: "0%", width: 6, animationDelay: "-1.1s" },
];

const BURST: CSSProperties[] = [
  { left: "62%", top: "8%", width: 12 },
  { left: "70%", top: "26%", width: 8, animationDelay: "80ms" },
  { left: "30%", top: "12%", width: 9, animationDelay: "140ms" },
];

function Sparkle({ className, style }: { className: string; style: CSSProperties }) {
  return (
    <svg viewBox="0 0 10 10" className={cn("absolute", className)} style={style}>
      <path d="M5 0l1.2 3.8L10 5 6.2 6.2 5 10 3.8 6.2 0 5l3.8-1.2z" fill="currentColor" />
    </svg>
  );
}

/** The large welcome mascot with its floating mini-orbs and sparkles. */
export function MascotScene({ mood = "idle", className }: { mood?: MascotMood; className?: string }) {
  return (
    <div
      aria-hidden
      data-mood={mood}
      className={cn(
        "mascot-scene relative flex h-40 w-64 items-center justify-center sm:h-48 sm:w-80 short:h-28 short:w-60",
        className,
      )}
    >
      {MINI_ORBS.map((orb, index) => (
        <span
          key={index}
          className={cn("mascot-mini absolute", orb.className)}
          style={{ ...orb.style, width: orb.size, height: orb.size, ["--tint" as string]: orb.tint }}
        >
          <span className="mascot-mini-eyes" />
        </span>
      ))}

      {SPARKLES.map((style, index) => (
        <Sparkle key={index} className="mascot-twinkle text-white/80" style={style} />
      ))}
      {BURST.map((style, index) => (
        <Sparkle key={index} className="mascot-burst text-mascot-cyan" style={style} />
      ))}

      <Mascot size="lg" mood={mood} interactive className="short:size-24" />
    </div>
  );
}
