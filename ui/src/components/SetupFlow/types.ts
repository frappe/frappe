/** One screen of an app's setup. The host renders it in the `#step` slot. */
export interface SetupStep {
  name: string;
  /** Cannot be skipped, and hides "Skip setup" while shown: setting a first password. */
  required?: boolean;
}

/** English defaults; pass translated text to relabel. */
export interface SetupFlowLabels {
  back: string;
  skip: string;
  skipTitle: string;
  skipMessage: string;
  cancel: string;
  stepOf: (step: number, total: number) => string;
}

export interface SetupFlowProps {
  steps: SetupStep[];
  labels?: Partial<SetupFlowLabels>;
  /** False hides the Back button in the header; the host renders its own from the
   * slot's `back` and `canGoBack`, say beside its step's actions. */
  backButton?: boolean;
}

/** What the setup ended with, for the host to save and act on. */
export interface SetupFlowResult {
  skipped: boolean;
  completed: string[];
  skippedSteps: string[];
}

/** Passed to the `#step` slot. */
export interface SetupStepSlotProps {
  step: SetupStep;
  index: number;
  /** Mark this step done and move on; details are added to its event. */
  done: (details?: Record<string, unknown>) => void;
  /** Leave this step for later and move on. */
  skip: () => void;
  /** Return to the previous step. Does nothing when `canGoBack` is false. */
  back: () => void;
  /** False on the first step and after a required one. */
  canGoBack: boolean;
}

export type ChoiceValue = string | number | boolean;

/** A chip in a ChoiceStep. `icon` is a CSS icon class, like `lucide-school`; apps with their own
 * icon components use the `#icon` slot instead. */
export interface ChoiceOption {
  label: string;
  value: ChoiceValue;
  icon?: string;
}

/** A row in a ListStep. */
export interface ListOption {
  label: string;
  value: ChoiceValue;
  description?: string;
  icon?: string;
}
