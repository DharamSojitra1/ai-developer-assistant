import { useId, useRef, useState } from "react";

import { cn } from "@/lib/cn";

import { useMascotEyes, useMascotReactions, useMascotWave } from "./useMascotEyes";

export type MascotMood = "idle" | "typing" | "waiting" | "thinking" | "speaking" | "happy" | "error";

const HOVER_HAPPY_MOODS: MascotMood[] = ["idle", "typing", "waiting"];

const INK = "#0b0d1a";
const HEAD_PATH = "M60 16C68 20 95 30 95 50c0 17-15 27-35 27S25 67 25 50c0-20 27-30 35-34z";
const HAND_PATH = "M43 86c-5-3-14-1-16 4-1 3 2 5 6 4 5-1 9-4 10-8z";
const FACE = { cx: 60, cy: 52, rx: 25, ry: 17.5 };
const EYES = [
  { cx: 50, side: "left" },
  { cx: 70, side: "right" },
] as const;
const EYE_CY = 52;
const EYE_RX = 5;
const EYE_RY = 6;

function stop(offset: string, color: string, opacity = 1) {
  return <stop key={offset} offset={offset} style={{ stopColor: color, stopOpacity: opacity }} />;
}

export function Mascot({
  mood = "idle",
  size = "sm",
  still = false,
  interactive = false,
  className,
}: {
  mood?: MascotMood;
  size?: "sm" | "lg";
  /** Skips idle blinking, for avatars that aren't the focus of attention. */
  still?: boolean;
  /** Follows the cursor on desktop and smiles on hover. */
  interactive?: boolean;
  /** For `sm`, this also sets the size (default `size-7`). */
  className?: string;
}) {
  const id = useId().replace(/:/g, "");
  const ref = (name: string) => `url(#${id}-${name})`;
  const large = size === "lg";
  const rootRef = useRef<HTMLSpanElement>(null);
  const [hovered, setHovered] = useState(false);

  useMascotEyes(rootRef, { blink: !still, track: interactive });
  useMascotWave(rootRef, large && interactive);
  useMascotReactions(rootRef, large && interactive);

  const shownMood: MascotMood = interactive && hovered && HOVER_HAPPY_MOODS.includes(mood) ? "happy" : mood;

  const svg = (
    <svg viewBox={large ? "0 0 120 120" : "22 1 76 76"} fill="none" className="mascot-svg size-full overflow-visible">
      <defs>
        <radialGradient id={`${id}-head`} gradientUnits="userSpaceOnUse" cx="46" cy="30" r="60">
          {stop("0", "#e6f0ff")}
          {stop("0.25", "var(--color-bot-light)")}
          {stop("0.62", "var(--color-bot)")}
          {stop("1", "var(--color-bot-deep)")}
        </radialGradient>
        <radialGradient id={`${id}-core`} gradientUnits="userSpaceOnUse" cx="52" cy="40" r="46">
          {stop("0.6", "#0d2a6b", 0)}
          {stop("1", "#0d2a6b", 0.45)}
        </radialGradient>
        <linearGradient id={`${id}-rim`} x1="0" y1="1" x2="0" y2="0">
          {stop("0", "var(--color-mascot-cyan)", 0.85)}
          {stop("0.4", "#ffffff", 0.15)}
          {stop("1", "#ffffff", 0)}
        </linearGradient>
        <linearGradient id={`${id}-gloss`} x1="0" y1="0" x2="0" y2="1">
          {stop("0", "#fff", 0.95)}
          {stop("1", "#fff", 0)}
        </linearGradient>
        {/* User-space so the eyelids can reuse the exact face shading. */}
        <linearGradient
          id={`${id}-visor`}
          gradientUnits="userSpaceOnUse"
          x1="0"
          y1={FACE.cy - FACE.ry}
          x2="0"
          y2={FACE.cy + FACE.ry}
        >
          {stop("0", "#9fb9e8", 0.55)}
          {stop("0.32", "#c9daf6", 0.12)}
          {stop("0.6", "#ffffff", 0)}
          {stop("1", "#d6e3fa", 0.35)}
        </linearGradient>
        <radialGradient id={`${id}-eye`} cx="35%" cy="30%" r="80%">
          {stop("0", "#3a3d52")}
          {stop("0.55", "#12131f")}
          {stop("1", "#030308")}
        </radialGradient>
        <radialGradient id={`${id}-bulb`} cx="35%" cy="30%" r="75%">
          {stop("0", "#eaf3ff")}
          {stop("0.45", "var(--color-bot)")}
          {stop("1", "var(--color-bot-deep)")}
        </radialGradient>
        {EYES.map((eye) => (
          <clipPath key={eye.side} id={`${id}-socket-${eye.side}`}>
            <ellipse cx={eye.cx} cy={EYE_CY} rx={EYE_RX} ry={EYE_RY} />
          </clipPath>
        ))}
        {large && (
          <>
            <radialGradient id={`${id}-part`} cx="35%" cy="30%" r="80%">
              {stop("0", "#e6f0ff")}
              {stop("0.3", "var(--color-bot-light)")}
              {stop("0.7", "var(--color-bot)")}
              {stop("1", "var(--color-bot-deep)")}
            </radialGradient>
            <radialGradient id={`${id}-shadow`} cx="50%" cy="50%" r="50%">
              {stop("0", "#000", 0.55)}
              {stop("1", "#000", 0)}
            </radialGradient>
          </>
        )}
      </defs>

      {large && <ellipse className="mascot-shadow" cx="60" cy="116" rx="20" ry="3.5" fill={ref("shadow")} />}

      <g className="mascot-body">
        {large && (
          <g data-part="body" className="bot-belly">
            <circle cx="60" cy="98" r="12" fill={ref("part")} />
            <ellipse cx="55.5" cy="92.5" rx="4" ry="2.2" transform="rotate(-25 55.5 92.5)" fill="#fff" opacity="0.7" />
            <circle cx="60" cy="99.5" r="3.6" fill={INK} opacity="0.12" />
            <circle cx="60" cy="99" r="3.6" fill="var(--color-bot-face)" />
          </g>
        )}

        <g className="bot-head">
          <g className="bot-antenna">
            <path d="M60 18V9" stroke="var(--color-bot)" strokeWidth="2.2" strokeLinecap="round" />
            <ellipse cx="60" cy="11.5" rx="3.8" ry="1.3" stroke="#fff" strokeWidth="1.2" />
            <circle className="bot-bulb" cx="60" cy="6" r="3.6" fill={ref("bulb")} />
            <circle cx="58.8" cy="4.8" r="1" fill="#fff" opacity="0.9" />
          </g>

          <path d={HEAD_PATH} fill={ref("head")} />
          <path d={HEAD_PATH} fill={ref("core")} />
          <path d={HEAD_PATH} stroke={ref("rim")} strokeWidth="1.4" />

          <g className="mascot-gloss">
            <ellipse cx="42" cy="30" rx="10" ry="4.5" transform="rotate(-28 42 30)" fill={ref("gloss")} />
            <ellipse cx="36.5" cy="35" rx="2" ry="1.2" transform="rotate(-50 36.5 35)" fill="#fff" opacity="0.85" />
          </g>

          <g className="bot-face">
            <ellipse {...FACE} fill="var(--color-bot-face)" />
            <ellipse {...FACE} fill={ref("visor")} />
            <ellipse {...FACE} stroke="#0d2a6b" strokeOpacity="0.18" strokeWidth="0.8" />

            <g className="mascot-eyes">
              <g className="mascot-eyes-open">
                <g className="mascot-look">
                  <g className="mascot-glance">
                    {EYES.map((eye) => (
                      // The clip moves with the eye, so the lid always matches its shape.
                      <g key={eye.side} clipPath={ref(`socket-${eye.side}`)}>
                        <ellipse cx={eye.cx} cy={EYE_CY} rx={EYE_RX} ry={EYE_RY} fill={ref("eye")} />
                        <ellipse cx={eye.cx + 1.6} cy={EYE_CY - 2.3} rx="1.9" ry="1.6" fill="#fff" />
                        <circle cx={eye.cx - 1.6} cy={EYE_CY + 2.5} r="0.8" fill="#fff" opacity="0.8" />
                        <g className={cn("mascot-lid", `mascot-lid-${eye.side}`)}>
                          <rect
                            x={eye.cx - 8}
                            y={EYE_CY - EYE_RY - 13}
                            width="16"
                            height="13"
                            fill="var(--color-bot-face)"
                          />
                        </g>
                      </g>
                    ))}
                  </g>
                </g>
              </g>
              <g className="mascot-eyes-happy" stroke={INK} strokeWidth={large ? 2.6 : 3.2} strokeLinecap="round">
                <path d="M45 54q5-6 10 0" />
                <path d="M65 54q5-6 10 0" />
              </g>
            </g>

            <ellipse className="mascot-mouth mascot-mouth-smile" cx="60" cy="60.5" rx="1.5" ry="1" fill={INK} />
            <path
              className="mascot-mouth mascot-mouth-happy"
              d="M52.5 59q7.5 5.5 15 0"
              stroke={INK}
              strokeWidth={large ? 1.8 : 2.4}
              strokeLinecap="round"
            />
            <ellipse className="mascot-mouth mascot-mouth-speaking" cx="60" cy="61" rx="2.4" ry="2" fill={INK} />
            <path
              className="mascot-mouth mascot-mouth-error"
              d="M55 62q1.25-1.5 2.5 0t2.5 0t2.5 0t2.5 0"
              stroke={INK}
              strokeWidth={large ? 1.5 : 2}
              strokeLinecap="round"
            />
          </g>
        </g>

        {large && (
          <g data-part="hands">
            <path className="bot-hand bot-hand-left" d={HAND_PATH} fill={ref("part")} />
            <g transform="translate(120 0) scale(-1 1)">
              <path className="bot-hand bot-hand-right" d={HAND_PATH} fill={ref("part")} />
            </g>
          </g>
        )}
      </g>
    </svg>
  );

  return (
    <span
      ref={rootRef}
      aria-hidden
      data-mood={shownMood}
      data-still={still || undefined}
      data-size={size}
      onPointerEnter={interactive ? () => setHovered(true) : undefined}
      onPointerLeave={interactive ? () => setHovered(false) : undefined}
      className={cn(
        "mascot relative inline-flex shrink-0 items-center justify-center",
        large ? "mascot--lg size-28 sm:size-34" : (className ?? "size-7"),
        large && className,
        large && interactive && "cursor-pointer",
      )}
    >
      <span className="mascot-tilt relative size-full">{svg}</span>
    </span>
  );
}
