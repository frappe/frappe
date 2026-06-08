import { InputLabelingProps } from "../types";

export interface LinkProps extends InputLabelingProps {
  doctype: string;
  filters?: Record<string, unknown>;
  creatable?: boolean;
  disabled?: boolean;
  placeholder?: string;
}

export type LinkEmits = {
  create: [query: string];
};

export interface LinkExposed {
  reload: () => void;
}

export type LinkOption = {
  label: string;
  value: string;
  description?: string;
};
