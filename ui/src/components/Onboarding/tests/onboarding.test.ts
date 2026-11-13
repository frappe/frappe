import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

// Hoisted so the factories passed to `vi.mock` can reference them.
const { createResourceMock } = vi.hoisted(() => ({
  createResourceMock: vi.fn(),
}));

vi.mock("frappe-ui", () => ({
  call: vi.fn(),
  createResource: createResourceMock,
}));

// A fresh ref per test, like a browser with no saved data.
vi.mock("@vueuse/core", () => ({
  useStorage: (_key: string, initial: unknown) => ref(initial),
}));

vi.mock("../../../utils/session", () => ({
  sessionUser: () => "jane@example.com",
}));

const steps = () => [
  {
    name: "create_first_lead",
    title: "Create your first lead",
    completed: false,
  },
  { name: "invite_team", title: "Invite your team", completed: false },
];

async function load() {
  const { useOnboarding } = await import("../onboarding");
  const { showHelpModal } = await import("../help");
  const { showHelpCenter } = await import("../helpCenter");
  const onboarding = useOnboarding("frappecrm")!;
  const onStatusLoaded = createResourceMock.mock.calls.at(-1)?.[0].onSuccess;
  return { onboarding, showHelpModal, showHelpCenter, onStatusLoaded };
}

describe("useOnboarding", () => {
  beforeEach(() => {
    vi.resetModules();
    createResourceMock.mockReset();
  });

  it("closes the panel once the saved status shows onboarding is finished", async () => {
    const { onboarding, showHelpModal, onStatusLoaded } = await load();

    onboarding.setUp(steps());
    // opened before the saved status is known
    expect(showHelpModal.value).toBe(true);

    onStatusLoaded({
      frappecrm_onboarding_status: steps().map((s) => ({
        name: s.name,
        completed: true,
      })),
    });
    expect(showHelpModal.value).toBe(false);
  });

  it("keeps the panel open when the saved status still has steps to do", async () => {
    const { onboarding, showHelpModal, onStatusLoaded } = await load();

    onboarding.setUp(steps());
    onStatusLoaded({
      frappecrm_onboarding_status: [
        { name: "create_first_lead", completed: true },
        { name: "invite_team", completed: false },
      ],
    });
    expect(showHelpModal.value).toBe(true);
  });

  it("opens the help centre after Skip all", async () => {
    const { onboarding, showHelpModal, showHelpCenter } = await load();

    onboarding.setUp(steps());
    onboarding.skipAll();

    // what HelpModal's "Help centre" item does
    onboarding.syncStatus();
    showHelpCenter.value = true;

    expect(showHelpModal.value).toBe(true);
  });

  it("matches saved progress to steps by name, not position", async () => {
    const { onboarding, onStatusLoaded } = await load();

    const shown = [
      { name: "invite_team", title: "Invite your team", completed: false },
      { name: "add_a_task", title: "Add a task", completed: false },
      {
        name: "create_first_lead",
        title: "Create your first lead",
        completed: false,
      },
    ];
    onboarding.setUp(shown);
    onStatusLoaded({
      frappecrm_onboarding_status: [
        { name: "create_first_lead", completed: true },
        { name: "invite_team", completed: false },
      ],
    });

    const done = shown.filter((s) => s.completed).map((s) => s.name);
    expect(done).toEqual(["create_first_lead"]);
    expect(onboarding.isOnboardingStepsCompleted.value).toBe(false);
  });

  it("stays finished when the app later adds a step", async () => {
    const { onboarding, onStatusLoaded, showHelpModal } = await load();

    const shown = [
      ...steps(),
      { name: "publish_first_lead", title: "Publish", completed: false },
    ];
    onboarding.setUp(shown);
    onStatusLoaded({
      frappecrm_onboarding_status: [
        { name: "create_first_lead", completed: true },
        { name: "invite_team", completed: true },
      ],
    });

    expect(onboarding.isOnboardingStepsCompleted.value).toBe(true);
    expect(showHelpModal.value).toBe(false);
  });

  it("does not save a queued step before the saved status is known", async () => {
    const { call } = await import("frappe-ui");
    const { onboarding, onStatusLoaded } = await load();
    vi.mocked(call).mockClear();

    const shown = steps();
    onboarding.updateOnboardingStep("invite_team");
    onboarding.setUp(shown);
    expect(shown.find((s) => s.name === "invite_team")?.completed).toBe(true);
    expect(vi.mocked(call)).not.toHaveBeenCalled();

    onStatusLoaded({
      frappecrm_onboarding_status: [{ name: "a_role_only_step", completed: true }],
    });
    const saved = JSON.parse(vi.mocked(call).mock.calls.at(-1)?.[1].steps);
    expect(saved).toContainEqual({ name: "invite_team", completed: true });
    expect(saved).toContainEqual({ name: "a_role_only_step", completed: true });
  });

  it("applies a step queued before setUp only once", async () => {
    const { call } = await import("frappe-ui");
    const { onboarding, onStatusLoaded } = await load();

    const shown = steps();
    onboarding.updateOnboardingStep("invite_team");
    onStatusLoaded({});
    onboarding.setUp(shown);
    onboarding.updateOnboardingStep("invite_team", false);
    onboarding.syncStatus();

    expect(shown.find((s) => s.name === "invite_team")?.completed).toBe(false);
    const saved = JSON.parse(vi.mocked(call).mock.calls.at(-1)?.[1].steps);
    expect(
      saved.find((s: { name: string }) => s.name === "invite_team")?.completed,
    ).toBe(false);
  });

  it("keeps a step completed before setUp, and saves it", async () => {
    const { call } = await import("frappe-ui");
    const { onboarding, onStatusLoaded } = await load();

    const shown = steps();
    onboarding.updateOnboardingStep("invite_team");
    onboarding.setUp(shown);
    onStatusLoaded({});

    expect(shown.find((s) => s.name === "invite_team")?.completed).toBe(true);
    const saved = JSON.parse(vi.mocked(call).mock.calls.at(-1)?.[1].steps);
    expect(saved).toEqual([
      { name: "create_first_lead", completed: false },
      { name: "invite_team", completed: true },
    ]);
  });

  it("keeps a step completed before setUp when the saved status loads first", async () => {
    const { onboarding, onStatusLoaded } = await load();

    const shown = steps();
    onboarding.updateOnboardingStep("invite_team");
    onStatusLoaded({});
    onboarding.setUp(shown);

    expect(shown.find((s) => s.name === "invite_team")?.completed).toBe(true);
  });
});
