export interface InputLabelingProps {
  label?: string;
  description?: string;
  error?: string | Error;
  required?: boolean;
}

/** Size scale for text-style inputs. */
export type InputSize = "sm" | "md" | "lg" | "xl";

/** Variant scale for text-style inputs that have a container surface. */
export type InputVariant = "subtle" | "outline" | "ghost";
