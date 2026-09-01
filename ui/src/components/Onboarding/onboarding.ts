import { call, createResource } from "frappe-ui";
import { useStorage } from "@vueuse/core";
import { computed, reactive } from "vue";
import { minimize, showHelpModal } from "./help";
import { sessionUser } from "../../utils/session";
import type {
  OnboardingBulkCallback,
  OnboardingStep,
  OnboardingStepCallback,
  UseOnboarding,
} from "./types";

type StoredStep = { name: string; completed: boolean };
type StoredStatus = Record<string, Record<string, StoredStep[]>>;

const onboardings = reactive<Record<string, OnboardingStep[]>>({});
const onboardingStatus = useStorage<StoredStatus>("onboardingStatus", {});

/**
 * Read and write the signed-in user's getting-started checklist for one app.
 *
 * Returns `undefined` when nobody is signed in, so call sites have to guard —
 * the banner and the modal are not rendered for guests.
 */
export function useOnboarding(appName: string): UseOnboarding | undefined {
  const user = sessionUser();

  if (!user || user === "Guest") return;

  // `updateOnboardingStep` and `updateAll` are hoisted function declarations, so
  // TypeScript does not carry the guard above into them. This const does.
  const userId: string = user;

  const isOnboardingStepsCompleted = useStorage(
    "isOnboardingStepsCompleted" + appName + userId,
    false,
  );

  const onboardingSteps = computed<StoredStep[]>(
    () =>
      onboardingStatus.value?.[userId]?.[appName + "_onboarding_status"] || [],
  );

  if (!onboardingSteps.value.length && !isOnboardingStepsCompleted.value) {
    createResource({
      url: "frappe.onboarding.get_onboarding_status",
      cache: "onboarding_status",
      auto: true,
      onSuccess: (data: Record<string, StoredStep[]>) => {
        onboardingStatus.value[userId] = data;
        syncStatus();
      },
    });
  }

  const stepsCompleted = computed(
    () => onboardings[appName]?.filter((step) => step.completed).length || 0,
  );
  const totalSteps = computed(() => onboardings[appName]?.length || 0);

  const completedPercentage = computed(() =>
    Math.floor((stepsCompleted.value / totalSteps.value) * 100),
  );

  function skip(step: string, callback: OnboardingStepCallback | null = null) {
    updateOnboardingStep(step, true, true, callback);
  }

  function skipAll(callback: OnboardingBulkCallback | null = null) {
    updateAll(true, callback);
  }

  function reset(step: string, callback: OnboardingStepCallback | null = null) {
    updateOnboardingStep(step, false, false, callback);
  }

  function resetAll(callback: OnboardingBulkCallback | null = null) {
    updateAll(false, callback);
  }

  function updateOnboardingStep(
    step: string,
    value = true,
    skipped = false,
    callback: OnboardingStepCallback | null = null,
  ) {
    if (isOnboardingStepsCompleted.value) return;

    if (!onboardingSteps.value.length) {
      if (!onboardingStatus.value[userId]) {
        onboardingStatus.value[userId] = {};
      }
      onboardingStatus.value[userId][appName + "_onboarding_status"] =
        onboardings[appName].map((s) => {
          return { name: s.name, completed: false };
        });
    }

    let index = onboardingSteps.value.findIndex((s) => s.name === step);
    if (index !== -1) {
      onboardingSteps.value[index].completed = value;
      onboardings[appName][index].completed = value;
    }

    updateUserOnboardingStatus(onboardingSteps.value);

    callback?.(step, skipped);

    minimize.value = false;
  }

  function updateAll(
    value: boolean,
    callback: OnboardingBulkCallback | null = null,
  ) {
    if (isOnboardingStepsCompleted.value && value) return;

    if (!onboardingSteps.value.length) {
      if (!onboardingStatus.value[userId]) {
        onboardingStatus.value[userId] = {};
      }

      onboardingStatus.value[userId][appName + "_onboarding_status"] =
        onboardings[appName].map((s) => {
          return { name: s.name, completed: value };
        });
    } else {
      onboardingSteps.value.forEach((step) => {
        step.completed = value;
      });
    }

    onboardings[appName].forEach((step) => {
      step.completed = value;
    });

    updateUserOnboardingStatus(onboardingSteps.value);

    callback?.(value);
  }

  function updateUserOnboardingStatus(steps: StoredStep[]) {
    call("frappe.onboarding.update_user_onboarding_status", {
      steps: JSON.stringify(steps),
      appName,
    });
  }

  function syncStatus() {
    if (isOnboardingStepsCompleted.value) return;

    if (onboardingSteps.value.length) {
      let _steps = onboardingSteps.value;
      _steps.forEach((step, index) => {
        const onboardingExists =
          onboardings[appName] && onboardings[appName][index];
        if (onboardingExists) {
          onboardings[appName][index].completed = step.completed;
        }
      });
      isOnboardingStepsCompleted.value = _steps.every((step) => step.completed);
    } else {
      isOnboardingStepsCompleted.value = false;
    }
  }

  function setUp(steps: OnboardingStep[]) {
    showHelpModal.value = !isOnboardingStepsCompleted.value;

    if (onboardings[appName]) return;

    onboardings[appName] = steps;
    syncStatus();
  }

  return {
    steps: onboardings[appName],
    stepsCompleted,
    totalSteps,
    completedPercentage,
    isOnboardingStepsCompleted,
    updateOnboardingStep,
    skip,
    skipAll,
    reset,
    resetAll,
    setUp,
    syncStatus,
  };
}
