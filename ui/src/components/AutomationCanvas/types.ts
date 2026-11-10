import type { Component } from "vue";

/** A node's identity colour: its tab, hairline and selection. */
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

export type AutomationCanvasIssueLevel = "error" | "warning";

/** Something wrong with a node: a warning reads "Needs setup", an error "Has errors"; the message shows on hover. */
export interface AutomationCanvasIssue {
  level: AutomationCanvasIssueLevel;
  message: string;
}

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
  issue?: AutomationCanvasIssue;
  run?: AutomationCanvasRun;
  dimmed?: boolean;
  branching?: boolean;
  terminal?: boolean;
  /** Branch arms that have nothing in them yet. */
  arms?: AutomationCanvasArm[];
  /** Offer a step that runs once every arm of this branch has finished. */
  canContinue?: boolean;
}

/** How a trial run left a node. */
export interface AutomationCanvasRun {
  status: AutomationCanvasStatus;
  /** The run took this branch regardless of its condition. */
  forced?: boolean;
  /** Arms the run skipped and can still run. */
  retryArms?: AutomationCanvasArm[];
  /** How long the node took, shown in its footer. */
  durationMs?: number;
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
  label?: string;
  animated?: boolean;
  style?: Record<string, string | number>;
}

export interface AutomationCanvasPickerOption {
  value: string;
  label: string;
  description?: string;
  icon?: string | Component;
  tone?: AutomationCanvasTone;
  [key: string]: unknown;
}

export interface AutomationCanvasOptionGroup {
  group: string;
  options: AutomationCanvasPickerOption[];
}

export interface AutomationCanvasProps {
  nodes: AutomationCanvasNode[];
  edges: AutomationCanvasEdge[];
  selectedId?: string;
  startOptions?: AutomationCanvasOptionGroup[];
  blockOptions?: AutomationCanvasOptionGroup[];
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

export interface AutomationCanvasMovePayload {
  nodeId: string;
  position: { x: number; y: number };
}

export interface AutomationCanvasRunBranchPayload {
  nodeId: string;
  arm: AutomationCanvasArm;
}

export interface AutomationCanvasEmits {
  select: [nodeId: string];
  "pick-start": [value: string];
  "add-node": [payload: AutomationCanvasAddNodePayload];
  "run-branch": [payload: AutomationCanvasRunBranchPayload];
  /** A node was dragged; store the position to keep it. */
  move: [payload: AutomationCanvasMovePayload];
}
