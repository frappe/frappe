import { computed } from "vue";
import type { FieldComponentProps } from "./types";

/** What a frappe-ui input draws around its control: the label, description and error text, or in a panel row only a ghost box the row fills in. */
export function useInputFrame(props: FieldComponentProps) {
  return computed(() =>
    props.panel
      ? { variant: "ghost", size: "sm", "aria-invalid": props.error?.length ? true : undefined }
      : { label: props.field.label, description: props.field.description, error: props.error }
  );
}
