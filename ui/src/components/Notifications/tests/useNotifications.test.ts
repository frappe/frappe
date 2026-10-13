import { describe, expect, it, vi } from "vitest";

const unreadCount = vi.hoisted(() => ({ data: 0, reload: vi.fn() }));

vi.mock("frappe-ui", () => ({
  call: vi.fn(),
  createListResource: () => ({ data: [], reload: vi.fn() }),
  createResource: () => unreadCount,
}));

import { useNotifications } from "../useNotifications";

describe("useNotifications", () => {
  it("reload refreshes the unread count", () => {
    const notifications = useNotifications({
      currentUser: "test@example.com",
    });

    notifications.reload();

    expect(unreadCount.reload).toHaveBeenCalledOnce();
  });
});
