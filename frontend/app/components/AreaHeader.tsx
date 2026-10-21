import Link from "next/link";
import type { ReactNode } from "react";

/**
 * Page header for the four existing learning areas and the Sandbox
 * (SPEC-014 F3). One `h1` (page-title tier), a role line that says what
 * the area is for, an optional lede, and one hand-off link to the next
 * area (§3 of the spec). The next-step target must be an implemented
 * route; unbuilt areas are plain text "(planned)" per DESIGN.md §12.
 */
export function AreaHeader({
  title,
  role,
  lede,
  next,
  children,
}: {
  title: string;
  role: string;
  lede?: ReactNode;
  next?: { href: string; label: string } | null;
  children?: ReactNode;
}) {
  return (
    <header className="flex flex-col gap-2 border-b border-hairline pb-4">
      <p className="font-mono text-meta uppercase text-secondary">{role}</p>
      <h1 className="text-page-title text-primary">{title}</h1>
      {lede && <p className="max-w-3xl text-lede text-secondary">{lede}</p>}
      {next && (
        <p className="text-body text-secondary">
          Next:{" "}
          <Link
            href={next.href}
            className="text-primary underline underline-offset-2 hover:opacity-80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary"
          >
            {next.label}
          </Link>
        </p>
      )}
      {children}
    </header>
  );
}
