import type { InputLabelingProps as AtomLabelingProps } from "frappe-ui";
import { InputLabelingProps } from "../types";

export interface LinkProps extends Omit<InputLabelingProps, "error"> {
  error?: AtomLabelingProps["error"];
  doctype: string;
  filters?: Record<string, unknown>;
  creatable?: boolean;
  redirectable?: boolean;
  editable?: boolean;
  disabled?: boolean;
  placeholder?: string;
  /** What the current value displays as until the search returns it. */
  title?: string;
  /** Label options by the record's name (its ID) rather than its title. The
   *  search still matches titles server-side, so client filtering is off. */
  idLabels?: boolean;
}

export interface LinkSlots {
  /** Content rendered in the input's suffix region. Scoped. */
  suffix?: (props: Record<string, unknown>) => any;
  /** Custom render for the "Create New" option; receives the typed query. */
  "item-create"?: (props: { query: string }) => any;
}

export type LinkEmits = {
  create: [query: string];
  redirect: [value: string];
  edit: [value: string];
};

export interface LinkExposed {
  reload: () => void;
}

export type LinkOption = {
  label: string;
  value: string;
  description?: string;
};
