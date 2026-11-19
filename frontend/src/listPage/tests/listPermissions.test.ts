// The list's rights: a right on another doctype settles through that doctype's meta, one on the list's doctype through its own.
import { describe, expect, it, vi } from "vitest";
import { ref } from "vue";

const loading = ref(true);
const other = vi.hoisted(() => ({ passes: vi.fn(() => true), settled: vi.fn(() => Promise.resolve()) }));

vi.mock("@framework/ui/useDocPermissions", () => ({ useDocPermissions: () => ({ holds: () => true, loading }) }));
vi.mock("@framework/ui/useSession", () => ({ useSession: () => ({ session: ref({ user: { name: "Administrator" } }) }) }));
vi.mock("@framework/ui/useUserRoles", () => ({ useUserRoles: () => ({ roles: ref([]) }) }));
vi.mock("@/createRight", () => ({ useCreateRight: () => ref(true) }));
vi.mock("@/acts/doctypeRight", async (original) => ({
  ...(await original<typeof import("@/acts/doctypeRight")>()),
  doctypeRight: other,
}));

import { useListPermissions } from "../listPermissions";

describe("the list permissions' settled", () => {
  it("waits for the list doctype's meta on a name and on the doctype's own object form", async () => {
    const permissions = useListPermissions("Contact");
    loading.value = true;

    for (const right of ["write", { doctype: "Contact", ptype: "write" }] as const) {
      const waiting = permissions.settled(right);
      expect(waiting).toBeInstanceOf(Promise);
    }
    loading.value = false;
    expect(permissions.settled("write")).toBeUndefined();
    expect(other.settled).not.toHaveBeenCalled();
  });

  it("hands another doctype's right to that doctype's own read", () => {
    const permissions = useListPermissions("Contact");
    const right = { doctype: "Address", ptype: "read" } as const;

    expect(permissions.settled(right)).toBeInstanceOf(Promise);
    expect(other.settled).toHaveBeenCalledWith(right);
    expect(permissions.passes(right)).toBe(true);
  });
});
