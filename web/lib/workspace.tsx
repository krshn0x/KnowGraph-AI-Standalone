"use client";

import { createContext, useContext, type Dispatch, type SetStateAction } from "react";
import type { ChatEntry, Entity, Evidence, Health, Investigation, View } from "./types";

export interface Resource<T> { data?: T; error?: string; loading: boolean }
export interface Workspace {
  health: Resource<Health>; incidents: Resource<Entity[]>; services: Resource<Entity[]>;
  investigation: Resource<Investigation>; selectedId: string; selectIncident: (id: string) => void;
  lookback: number; setLookback: (hours: number) => void;
  revision: number; refresh: () => void; imported: () => void;
  inspect: (entity: Entity) => void; navigate: (view: View) => void;
  latestEvidence: Evidence; setLatestEvidence: (evidence: Evidence) => void;
  notify: (message: string) => void;
  configureAI: () => void;
  chat: ChatEntry[]; setChat: Dispatch<SetStateAction<ChatEntry[]>>;
  askPending: boolean; setAskPending: (pending: boolean) => void;
  chatError: string; setChatError: (error: string) => void;
}
export const WorkspaceContext = createContext<Workspace | null>(null);
export function useWorkspace() {
  const workspace = useContext(WorkspaceContext);
  if (!workspace) throw new Error("Workspace provider is missing");
  return workspace;
}
