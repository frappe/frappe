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
  darkMode: string;
  lightMode: string;
  stepOf: (step: number, total: number) => string;
}

export interface SetupFlowProps {
  steps: SetupStep[];
  labels?: Partial<SetupFlowLabels>;
  /** False hides the Back button in the header; the host renders its own from the
   * slot's `back` and `canGoBack`, say beside its step's actions. */
  backButton?: boolean;
  /** Which side the `#preview` slot sits on from `lg` up. Below `lg` it is hidden. */
  previewSide?: "start" | "end";
  /** False hides the light and dark switch in the header, for an app without a dark mode. */
  themeToggle?: boolean;
}

/** Passed to the `#preview` slot. */
export interface SetupPreviewSlotProps {
  step: SetupStep;
  index: number;
  /** SetupFlow's `previewSide`, to pass on as `<SetupPreviewFrame :side>`. */
  side: "start" | "end";
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
  /** Return to the previous screen: inside the step when it handles Back, else the previous
   * step. Does nothing when `canGoBack` is false. */
  back: () => void;
  /** False on the first step and after a required one, unless the step can go back itself. */
  canGoBack: boolean;
  /** A step with screens of its own hands over its Back here, so the flow's Back goes to its
   * previous screen first. Pass null to give Back to the flow again. */
  handleBack: (handler: StepBack | null) => void;
}

/** A step's own Back, for a step with several screens. `canGoBack` is read reactively. */
export interface StepBack {
  canGoBack: () => boolean;
  back: () => void;
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
