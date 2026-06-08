import { InputLabelingProps, InputSize, InputVariant } from "../types";

/** Variants supported by the control — a subset of the shared `InputVariant` scale. */
export type PhoneInputVariant = Exclude<InputVariant, "ghost">;

export interface Country {
  /** Display name, e.g. "India". */
  name: string;

  /** ISO2 code, e.g. "in". */
  code: string;

  /** International dialing code, e.g. "+91". */
  isd: string;
}

export interface PhoneInputProps extends InputLabelingProps {
  /**
   * Country pre-selected when the value is empty — an ISO2 code (`"in"`),
   * a dial code (`"+91"` or `"91"`), or a country name (`"India"`).
   * Defaults to the country of the system timezone; when neither resolves,
   * no country is selected.
   */
  defaultCountry?: string;

  /** Visual size of the control. */
  size?: InputSize;

  /** Style variant of the control. */
  variant?: PhoneInputVariant;

  /** Placeholder text for the number input. */
  placeholder?: string;

  /** Disables the country picker and the number input. */
  disabled?: boolean;
}

export interface PhoneInputSlots {
  /** Overrides the rendered label content. Receives `{ required }`. */
  label?: (props: { required: boolean }) => any;

  /** Overrides the rendered description content. */
  description?: () => any;

  /** Content rendered at the end of the control shell. */
  suffix?: () => any;
}
