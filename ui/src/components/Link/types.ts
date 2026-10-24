import { InputLabelingProps } from "../types";

export interface LinkProps extends InputLabelingProps {
  doctype: string;
  filters?: Record<string, unknown>;
  creatable?: boolean;
  /** The current record's address; with one, the field shows an arrow that opens it. */
  href?: string | null;
  editable?: boolean;
  disabled?: boolean;
  placeholder?: string;
  /** What the current value displays as until the search returns it. */
  title?: string;
}

export interface LinkSlots {
  /** Content rendered in the input's suffix region. Scoped. */
  suffix?: (props: Record<string, unknown>) => any;
  /** Custom render for the "Create New" option, always the last row; receives the typed query. */
  "item-create"?: (props: { query: string }) => any;
}

export type LinkEmits = {
  create: [query: string];
  /** A plain click on the arrow; a modified click is left to the browser. */
  redirect: [value: string];
  edit: [value: string];
};

export interface LinkExposed {
  reload: () => void;
  /** `fresh` skips the browser's cached answer and replaces it. */
  search: (text: string, options?: { fresh?: boolean }) => void;
  focus: () => void;
}

export type LinkOption = {
  label: string;
  value: string;
  description?: string;
};
