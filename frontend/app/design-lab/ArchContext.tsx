"use client";

import { createContext, useContext, useState, type ReactNode } from "react";

import type { ArchitectureId } from "../lib/infrastructureMapData";

/**
 * The architecture the learner is currently looking at. The signal-path
 * rail draws this architecture's own main path, so it never implies one
 * universal chain (SST is optional; see DESIGN.md revision D3).
 */
interface Ctx {
  arch: ArchitectureId;
  setArch: (id: ArchitectureId) => void;
}

const ArchCtx = createContext<Ctx>({ arch: "conventional-ac", setArch: () => {} });

export function ArchProvider({ children }: { children: ReactNode }) {
  const [arch, setArch] = useState<ArchitectureId>("conventional-ac");
  return <ArchCtx.Provider value={{ arch, setArch }}>{children}</ArchCtx.Provider>;
}

export function useArch() {
  return useContext(ArchCtx);
}
