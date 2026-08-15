import type { Component } from "vue";

export type AutomationCanvasTone =
  | "trigger"
  | "action"
  | "wait"
  | "event"
  | "condition";

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
  branching?: boolean;
  terminal?: boolean;
  arms?: AutomationCanvasArm[];
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
}

export interface AutomationCanvasOption {
  value: string;
  label: string;
  description?: string;
  icon?: string | Component;
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

export interface AutomationCanvasEmits {
  select: [nodeId: string];
  "pick-start": [value: string];
  "add-node": [payload: AutomationCanvasAddNodePayload];
}
