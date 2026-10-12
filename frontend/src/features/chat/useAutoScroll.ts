import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

/** How close to the bottom (px) still counts as "following" new content. */
const FOLLOW_THRESHOLD_PX = 96;

/**
 * Follows new content only while the reader is near the bottom, so reading
 * older messages is never interrupted by a streaming response.
 */
export function useAutoScroll(
  contentKey: unknown,
  enabled: boolean,
  { turnKey, anchorToLastMessage = false }: { turnKey?: string; anchorToLastMessage?: boolean } = {},
) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const followingRef = useRef(true);
  const turnKeyRef = useRef(turnKey);
  const [atBottom, setAtBottom] = useState(true);

  useEffect(() => {
    const container = containerRef.current;
    const sentinel = sentinelRef.current;
    followingRef.current = true;
    setAtBottom(true);
    if (!enabled || !container || !sentinel || typeof IntersectionObserver === "undefined") return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        followingRef.current = entry.isIntersecting;
        setAtBottom(entry.isIntersecting);
      },
      { root: container, rootMargin: `0px 0px ${FOLLOW_THRESHOLD_PX}px 0px`, threshold: 0 },
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [enabled]);

  // Runs before paint, so following content never visibly lags a frame.
  useLayoutEffect(() => {
    const container = containerRef.current;
    // A new question always brings the reader back to the latest message.
    if (turnKey !== turnKeyRef.current) {
      turnKeyRef.current = turnKey;
      followingRef.current = true;
    }
    if (!container || !followingRef.current) return;

    let target = container.scrollHeight;

    // A reply that arrives all at once is read from its start, not its end.
    const last = anchorToLastMessage ? container.querySelector("article:last-of-type") : null;
    if (last) {
      const lastTop = last.getBoundingClientRect().top - container.getBoundingClientRect().top + container.scrollTop;
      target = Math.min(target, lastTop - 16);
    }

    container.scrollTop = target;
  }, [contentKey, turnKey, anchorToLastMessage]);

  const scrollToBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
    const container = containerRef.current;
    if (!container) return;
    followingRef.current = true;
    container.scrollTo({ top: container.scrollHeight, behavior });
  }, []);

  return { containerRef, sentinelRef, atBottom, scrollToBottom };
}
