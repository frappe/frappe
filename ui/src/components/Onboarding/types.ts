import type { Component, ComputedRef, Ref } from "vue";

/** One item in an app's getting-started checklist. */
export interface OnboardingStep {
  /** Stable id, stored on the server and used by `skip` / `reset`. */
  name: string;
  /** Whether the user has finished (or skipped) this step. */
  completed: boolean;
  /** Text shown in the list. */
  title?: string;
  /** Icon component rendered before the title. */
  icon?: Component;
  /** `name` of a step that has to be completed before this one unlocks. */
  dependsOn?: string;
  /** Run when the user clicks the row. */
  onClick?: () => void;
  [key: string]: any;
}

/** Called after a step's state changes on the server. */
export type OnboardingStepCallback = (step: string, skipped: boolean) => void;

/** Called after every step's state changes at once. */
export type OnboardingBulkCallback = (value: boolean) => void;

/** What `useOnboarding` hands back for one app. */
export interface UseOnboarding {
  /** The steps registered by `setUp`, in order. */
  steps: OnboardingStep[] | undefined;
  /** How many steps are completed. */
  stepsCompleted: ComputedRef<number>;
  /** How many steps there are. */
  totalSteps: ComputedRef<number>;
  /** Completed share, rounded down, 0–100. */
  completedPercentage: ComputedRef<number>;
  /** True once every step is done. Persisted in localStorage. */
  isOnboardingStepsCompleted: Ref<boolean>;
  /** Mark one step completed (or not) and sync it to the server. */
  updateOnboardingStep: (
    step: string,
    value?: boolean,
    skipped?: boolean,
    callback?: OnboardingStepCallback | null,
  ) => void;
  /** Mark one step completed without the user doing it. */
  skip: (step: string, callback?: OnboardingStepCallback | null) => void;
  /** Mark every step completed. */
  skipAll: (callback?: OnboardingBulkCallback | null) => void;
  /** Mark one step not completed. */
  reset: (step: string, callback?: OnboardingStepCallback | null) => void;
  /** Mark every step not completed. */
  resetAll: (callback?: OnboardingBulkCallback | null) => void;
  /** Register this app's steps. Call once, before rendering the banner or modal. */
  setUp: (steps: OnboardingStep[]) => void;
  /** Re-read the stored status into the registered steps. */
  syncStatus: () => void;
}

/** Props for `<GettingStartedBanner>`. */
export interface GettingStartedBannerProps {
  /** Render the collapsed, icon-only form used by a collapsed sidebar. */
  isSidebarCollapsed?: boolean;
  /** App the onboarding status belongs to, e.g. `"frappecrm"`. */
  appName?: string;
}

/** One slide in an `<IntermediateStepModal>`. */
export interface IntermediateStep {
  /** Dialog title. */
  title?: string;
  /** Body copy. */
  message?: string;
  /** MP4 shown under the message. */
  videoURL?: string;
  /** Label of the single action button. */
  buttonLabel?: string;
  /** Run when the action button is clicked. */
  onClick?: () => void;
}

/** Props for `<IntermediateStepModal>`. */
export interface IntermediateStepModalProps {
  /** The step being shown. */
  currentStep?: IntermediateStep;
  /** Passed straight to `Dialog`'s `options`; overrides the derived options. */
  dialogOptions?: Record<string, any>;
}

/** Slots for `<IntermediateStepModal>`. */
export interface IntermediateStepModalSlots {
  /** Replaces the message + video body. */
  default?: () => any;
  /** Extra content above the body. */
  "body-header"?: () => any;
  /** Replaces the dialog's action row. */
  actions?: () => any;
}

/** One article group in the help centre list. */
export interface HelpArticle {
  /** Group heading. */
  title: string;
  /** Pages inside the group. */
  subArticles: { name: string; title: string }[];
  /** Whether the group is expanded. */
  opened?: boolean;
}

/** Props for `<HelpModal>`. */
export interface HelpModalProps {
  /** App the onboarding status belongs to, e.g. `"frappecrm"`. */
  appName?: string;
  /** Product name shown in the "Welcome to …" heading. */
  title?: string;
  /** Logo component shown above the heading. */
  logo: Component;
  /** Run after a single step is skipped. */
  afterSkip?: OnboardingStepCallback;
  /** Run after every step is skipped. */
  afterSkipAll?: OnboardingBulkCallback;
  /** Run after a single step is reset. */
  afterReset?: OnboardingStepCallback;
  /** Run after every step is reset. */
  afterResetAll?: OnboardingBulkCallback;
  /** Base URL articles open against. */
  docsLink?: string;
}

/** Props for `<OnboardingSteps>` — internal to `<HelpModal>`. */
export interface OnboardingStepsProps {
  appName?: string;
  title?: string;
  logo: Component;
  afterSkip?: OnboardingStepCallback;
  afterSkipAll?: OnboardingBulkCallback;
  afterReset?: OnboardingStepCallback;
  afterResetAll?: OnboardingBulkCallback;
}

/** Props for `<HelpCenter>` — internal to `<HelpModal>`. */
export interface HelpCenterProps {
  docsLink?: string;
}
