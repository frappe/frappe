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

export type AutomationCanvasIssueLevel = "error" | "warning";

/** Something wrong with a node, shown as a coloured border and an icon with this message. */
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

export interface AutomationCanvasRunBranchPayload {
  nodeId: string;
  arm: AutomationCanvasArm;
}

export interface AutomationCanvasEmits {
  select: [nodeId: string];
  "pick-start": [value: string];
  "add-node": [payload: AutomationCanvasAddNodePayload];
  "run-branch": [payload: AutomationCanvasRunBranchPayload];
}
