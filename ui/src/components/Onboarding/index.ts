// Onboarding and the help modal are one module: `onboarding.ts` drives the
// modal's open state, and `HelpModal` renders the step list. They moved out of
// `frappe-ui/frappe` together for that reason.
//
// `OnboardingSteps`, `HelpCenter` and `showHelpCenter` stay internal —
// `frappe-ui/frappe` exported them, but no app imports them and they are only
// ever rendered by `HelpModal`.
export { default as GettingStartedBanner } from "./GettingStartedBanner.vue";
export { default as HelpModal } from "./HelpModal.vue";
export { default as IntermediateStepModal } from "./IntermediateStepModal.vue";
export { useOnboarding } from "./onboarding";
export { minimize, showHelpModal } from "./help";
export type {
  GettingStartedBannerProps,
  HelpArticle,
  HelpModalProps,
  IntermediateStep,
  IntermediateStepModalProps,
  IntermediateStepModalSlots,
  OnboardingBulkCallback,
  OnboardingStep,
  OnboardingStepCallback,
  UseOnboarding,
} from "./types";
