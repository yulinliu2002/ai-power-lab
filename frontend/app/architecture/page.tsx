import type { Metadata } from "next";

import { ArchitectureChoices } from "../components/ArchitectureChoices";

export const metadata: Metadata = {
  title: "Architecture Choices | AI Power Lab",
};

/**
 * Architecture Choices (SPEC-011 content, SPEC-014 four-step flow). The
 * page is a thin server wrapper so the metadata stays server-side; all
 * interaction lives in `ArchitectureChoices`.
 */
export default function ArchitectureChoicesPage() {
  return <ArchitectureChoices />;
}
