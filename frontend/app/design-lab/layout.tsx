import type { Metadata } from "next";

import "./lab.css";
import { ArchProvider } from "./ArchContext";
import { LabNav } from "./LabNav";

export const metadata: Metadata = {
  title: "AI Power Lab — Design direction prototype",
  description: "Signal Path: design-direction prototype (not production).",
};

export default function LabLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="lab">
      <ArchProvider>
        <LabNav />
        <main>{children}</main>
      </ArchProvider>
      <footer className="lab-wrap" style={{ padding: "32px var(--lab-gutter) 48px", color: "var(--color-text-secondary)", fontSize: 12 }}>
        Design-direction prototype. Frontend-only: no engine, API or numeric changes. Not for production.
      </footer>
    </div>
  );
}
