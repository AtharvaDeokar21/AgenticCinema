"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";

/* Mirrors backend/app/shared/models/project.py — the same shared state the
   agents read from and write to. Here it holds whatever the current session
   has produced, so each agent can show the creator exactly which of its
   inputs are already satisfied and which are still missing. */
const empty = {
  project_id: null,
  creator_recommendations: null,
  script: null,
  storyboard: null,
  audio_master: null,
  sync_report: null,
  dub_tracks: null,
  clearance_report: null,
};

const ProjectContext = createContext(null);

export function ProjectProvider({ children }) {
  const [state, setState] = useState(() => ({
    ...empty,
    project_id: `proj_${Math.random().toString(36).slice(2, 9)}`,
  }));

  const write = useCallback((field, value) => {
    setState((prev) => ({ ...prev, [field]: value }));
  }, []);

  const reset = useCallback(() => {
    setState({ ...empty, project_id: `proj_${Math.random().toString(36).slice(2, 9)}` });
  }, []);

  const value = useMemo(() => ({ state, write, reset }), [state, write, reset]);
  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

export function useProject() {
  const context = useContext(ProjectContext);
  if (!context) throw new Error("useProject must be used inside <ProjectProvider>");
  return context;
}
