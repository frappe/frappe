import type { Component } from "vue";

/** Colour of a node's bare glyph. */
export type AutomationCanvasTone =
  | "blue"
  | "green"
  | "teal"
  | "amber"
  | "violet"
  | "cyan"
  | "orange"
  | "pink"
  | "red"
  | "gray"
  | "purple";

/** How a trial run left a node. */
export type AutomationCanvasStatus =
  | "running"
  | "Success"
  | "Skipped"
  | "Failed"
  | "Waiting";

export interface AutomationCanvasArm {
  key: string;
  label: string;
}

export interface AutomationCanvasNodeData {
  kicker: string;
  label: string;
  detail?: string;
  icon?: string | Component;
  tone?: AutomationCanvasTone;
  start?: boolean;
  empty?: boolean;
  error?: boolean;
  /** Why the node is not ready yet, shown as a warning tooltip. */
  incomplete?: string;
  status?: AutomationCanvasStatus;
  /** A trial run took this branch regardless of its condition. */
  forced?: boolean;
  dimmed?: boolean;
  branching?: boolean;
  terminal?: boolean;
  /** Branch arms that have nothing in them yet. */
  arms?: AutomationCanvasArm[];
  /** Offer a step that runs once every arm of this branch has finished. */
  canContinue?: boolean;
  /** Arms a trial run skipped and can still run. */
  retryArms?: AutomationCanvasArm[];
}

export interface AutomationCanvasNode {
  id: string;
  position: { x: number; y: number };
  data: AutomationCanvasNodeData;
}

export interface AutomationCanvasEdge {
  id: string;
  source: string;
  target: string;
  label?: string | null;
  animated?: boolean;
  style?: Record<string, string | number>;
}

export interface AutomationCanvasOption {
  value: string;
  label: string;
  description?: string;
  icon?: string | Component;
  tone?: AutomationCanvasTone;
  [key: string]: unknown;
}

export interface AutomationCanvasOptionGroup {
  group: string;
  options: AutomationCanvasOption[];
}

export interface AutomationCanvasProps {
  nodes: AutomationCanvasNode[];
  edges: AutomationCanvasEdge[];
  selectedId?: string;
  startOptions?: AutomationCanvasOptionGroup[];
  blockOptions?: AutomationCanvasOptionGroup[];
  /** Fade every node but the selected one, e.g. while it is being inspected. */
  dimUnselected?: boolean;
  canDelete?: boolean;
  canUndo?: boolean;
  canRedo?: boolean;
  readonly?: boolean;
}

export interface AutomationCanvasExposed {
  fitView: () => Promise<void>;
}

export interface AutomationCanvasAddNodePayload {
  afterId: string | null;
  branch: string | null;
  value: string;
}

export interface AutomationCanvasRunBranchPayload {
  nodeId: string;
  arm: AutomationCanvasArm;
}

export interface AutomationCanvasEmits {
  select: [nodeId: string];
  "pick-start": [value: string];
  "add-node": [payload: AutomationCanvasAddNodePayload];
  "request-remove": [nodeId: string];
  "run-branch": [payload: AutomationCanvasRunBranchPayload];
  undo: [];
  redo: [];
}
