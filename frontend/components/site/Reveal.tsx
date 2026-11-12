"use client";

import { useEffect, useRef, useState, type ElementType, type ReactNode } from "react";

/**
 * Fades and lifts its children in the first time they scroll into view.
 * Purely CSS-driven (.qc-reveal in globals.css); reduced motion shows the
 * content immediately. `delay` staggers siblings (ms).
 */
export default function Reveal({
  children,
  as: Tag = "div",
  delay = 0,
  className = "",
}: {
  children: ReactNode;
  as?: ElementType;
  delay?: number;
  className?: string;
}) {
  const ref = useRef<HTMLElement>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      setShown(true);
      return;
    }
    // Any visible pixel counts (tall blocks never reach a ratio threshold when
    // the page is jumped to). Content must never stay hidden, so a plain
    // scroll check backs up the observer, and anything already scrolled past
    // is shown too.
    const inView = () => el.getBoundingClientRect().top < window.innerHeight * 0.96;
    if (inView()) {
      setShown(true);
      return;
    }
    const done = () => {
      setShown(true);
      io.disconnect();
      window.removeEventListener("scroll", onScroll);
    };
    const onScroll = () => inView() && done();
    const io = new IntersectionObserver(
      (entries) => entries.some((e) => e.isIntersecting || e.boundingClientRect.top < 0) && done(),
      { rootMargin: "0px 0px -4% 0px", threshold: 0 },
    );
    io.observe(el);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      io.disconnect();
      window.removeEventListener("scroll", onScroll);
    };
  }, []);

  return (
    <Tag
      ref={ref}
      className={`qc-reveal ${className}`}
      data-shown={shown}
      style={delay ? { transitionDelay: `${delay}ms` } : undefined}
    >
      {children}
    </Tag>
  );
}
