import { call, createResource } from "frappe-ui";
import { useStorage } from "@vueuse/core";
import { computed, reactive } from "vue";
import { minimize, showHelpModal } from "./help";
import { showHelpCenter } from "./helpCenter";
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
// Steps completed before the app has called setUp, such as from a setup page that
// reloads into the app afterwards. Stored, so that reload does not lose them.
const pending = useStorage<Record<string, string[]>>("onboardingPending", {});
// Queued steps are kept until the saved status has loaded, so that load cannot undo them.
const statusLoaded: Record<string, boolean> = {};
const queueStep = (key: string, step: string) => {
  const queued = (pending.value[key] ||= []);
  if (!queued.includes(step)) queued.push(step);
};
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
  const pendingKey = `${userId}:${appName}`;

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
        statusLoaded[pendingKey] = true;
        syncStatus();
        // the panel opens before this status loads; close it if onboarding is already done
        if (isOnboardingStepsCompleted.value && !showHelpCenter.value)
          showHelpModal.value = false;
      },
    });
  } else {
    statusLoaded[pendingKey] = true;
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

    if (!onboardings[appName]) {
      if (value) queueStep(pendingKey, step);
      return;
    }

    const shown = onboardings[appName].find((s) => s.name === step);
    const saved = onboardingSteps.value.find((s) => s.name === step);
    if (shown) shown.completed = value;
    else if (saved) saved.completed = value;
    if (statusLoaded[pendingKey]) saveSteps();
    else if (value) queueStep(pendingKey, step);

    callback?.(step, skipped);

    minimize.value = false;
  }

  function updateAll(
    value: boolean,
    callback: OnboardingBulkCallback | null = null,
  ) {
    if ((isOnboardingStepsCompleted.value && value) || !onboardings[appName])
      return;

    onboardings[appName].forEach((step) => {
      step.completed = value;
      if (value && !statusLoaded[pendingKey]) queueStep(pendingKey, step.name);
    });
    if (statusLoaded[pendingKey]) saveSteps(value);

    callback?.(value);
  }

  // Saved by name: the app's steps in their current order, then any saved step it no
  // longer shows this user (a role-only step), so progress on it is not lost.
  function saveSteps(hiddenValue?: boolean) {
    const shown = onboardings[appName].map((s) => ({
      name: s.name,
      completed: Boolean(s.completed),
    }));
    const names = new Set(shown.map((s) => s.name));
    const hidden = onboardingSteps.value
      .filter((s) => !names.has(s.name))
      .map((s) => ({ ...s, completed: hiddenValue ?? s.completed }));
    const steps = [...shown, ...hidden];

    onboardingStatus.value[userId] ||= {};
    onboardingStatus.value[userId][appName + "_onboarding_status"] = steps;
    updateUserOnboardingStatus(steps);
  }

  function updateUserOnboardingStatus(steps: StoredStep[]) {
    call("frappe.onboarding.update_user_onboarding_status", {
      steps: JSON.stringify(steps),
      appName,
    });
  }

  function syncStatus() {
    if (isOnboardingStepsCompleted.value || !onboardings[appName]) return;

    const saved = new Map(
      onboardingSteps.value.map((s) => [s.name, s.completed]),
    );
    onboardings[appName].forEach((step) => {
      step.completed = saved.get(step.name) ?? false;
    });

    const queued = pending.value[pendingKey];
    queued?.forEach((name) => {
      const step = onboardings[appName].find((s) => s.name === name);
      if (step) step.completed = true;
    });
    // Saving replaces the whole saved list, so it waits for that list to be known.
    if (statusLoaded[pendingKey]) {
      if (queued?.length) saveSteps();
      delete pending.value[pendingKey];
    }

    // Finished stays finished: a checklist the user completed does not reopen when
    // the app later renames or adds steps.
    const everyShown = onboardings[appName].every((s) => s.completed);
    const everySaved = onboardingSteps.value.every((s) => s.completed);
    isOnboardingStepsCompleted.value =
      onboardingSteps.value.length > 0 && (everyShown || everySaved);
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
