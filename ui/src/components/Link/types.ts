import { InputLabelingProps } from "../types";

export interface LinkProps extends InputLabelingProps {
  doctype: string;
  filters?: Record<string, unknown>;
  creatable?: boolean;
  redirectable?: boolean;
  editable?: boolean;
  disabled?: boolean;
  placeholder?: string;
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
