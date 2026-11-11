import { computed } from "vue";
import type { FieldComponentProps } from "./types";

/** What a frappe-ui input draws around its control: the label, description and error text, or in a panel row only a ghost box the row fills in. */
export function useInputFrame(props: FieldComponentProps) {
  return computed(() =>
    props.panel
      ? {
          variant: "ghost",
          size: "sm",
          "aria-invalid": props.error?.length ? true : undefined,
          "aria-describedby": props.error?.length ? props.errorId : undefined,
        }
      : { label: props.field.label, description: props.field.description, error: props.error }
  );
}

interface PickerFrameOptions {
  /** Turns the field's description into what the picker shows; the field's own by default. */
  describe?: (description?: string) => string | undefined;
}

/**
 * The input frame of a picker; in a panel row its popover also opens below, left-aligned, and the control fills the box.
 * It has no `aria-invalid`: frappe-ui's pickers bind their own from `error`, which a panel row withholds.
 */
export function usePickerFrame(props: FieldComponentProps, options: PickerFrameOptions = {}) {
  const { describe = (description) => description } = options;
  const frame = useInputFrame(props);
  return computed(() => {
    if (!props.panel) return { ...frame.value, description: describe(props.field.description) };
    return {
      variant: "ghost",
      size: "sm",
      side: "bottom",
      align: "start",
      class: "w-full",
    };
  });
}
