import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

// Hoisted so the factory passed to `vi.mock` can reference it.
const { runMethod } = vi.hoisted(() => ({ runMethod: vi.fn() }));

vi.mock("../../../api", () => ({ runMethod }));

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

// Holds the saved-status read open so each test decides when it lands.
let resolveStatus: (value: { data: unknown }) => void = () => {};

async function load() {
  const { useOnboarding } = await import("../onboarding");
  const { showHelpModal } = await import("../help");
  const { showHelpCenter } = await import("../helpCenter");
  const onboarding = useOnboarding("frappecrm")!;
  const onStatusLoaded = async (data: unknown) => {
    resolveStatus({ data });
    await new Promise((resolve) => setTimeout(resolve, 0));
  };
  return { onboarding, showHelpModal, showHelpCenter, onStatusLoaded };
}

describe("useOnboarding", () => {
  beforeEach(() => {
    vi.resetModules();
    runMethod.mockReset();
    runMethod.mockImplementation((method: string) =>
      method === "frappe.onboarding.get_onboarding_status"
        ? new Promise((resolve) => (resolveStatus = resolve))
        : Promise.resolve({ data: null }),
    );
  });

  it("closes the panel once the saved status shows onboarding is finished", async () => {
    const { onboarding, showHelpModal, onStatusLoaded } = await load();

    onboarding.setUp(steps());
    // opened before the saved status is known
    expect(showHelpModal.value).toBe(true);

    await onStatusLoaded({
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
    await onStatusLoaded({
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
});
