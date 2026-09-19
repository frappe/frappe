// Mark-as-read: the row is saved whole, and only when it is still unread.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent } from "vue";
import { useNotifications } from "../useNotifications";
import type { NotificationStore } from "../types";

const api = vi.hoisted(() => ({
  listDocuments: vi.fn(),
  countDocuments: vi.fn(),
  updateDocument: vi.fn(),
  runMethod: vi.fn(),
  getSession: vi.fn(),
}));

vi.mock("../../../api", () => api);

function aRow(name: string, read: 0 | 1) {
  return { name, read, subject: name, modified: "2026-09-19 10:00:00" };
}

function mount(): NotificationStore {
  let controller: NotificationStore | null = null;
  const component = defineComponent({
    setup() {
      controller = useNotifications({ currentUser: "alice@example.com" });
      return () => null;
    },
  });
  createApp(component).mount(document.createElement("div"));
  return controller!;
}

beforeEach(() => {
  for (const fn of Object.values(api)) fn.mockReset();
  api.listDocuments.mockResolvedValue({
    data: [aRow("unread-1", 0), aRow("read-1", 1)],
    has_next_page: false,
  });
  api.countDocuments.mockResolvedValue({ data: 1 });
  api.updateDocument.mockResolvedValue({ data: {} });
  api.runMethod.mockResolvedValue({ data: {} });
});

describe("markAsRead", () => {
  it("saves the row and drops the unread count", async () => {
    const controller = mount();
    await vi.waitFor(() => expect(controller.notifications.length).toBe(2));

    await controller.markAsRead("unread-1");

    expect(api.updateDocument).toHaveBeenCalledTimes(1);
    expect(api.updateDocument).toHaveBeenCalledWith(
      "Notification Log",
      "unread-1",
      expect.objectContaining({ read: 1, modified: "2026-09-19 10:00:00" })
    );
  });

  it("costs no request for a row that is already read", async () => {
    const controller = mount();
    await vi.waitFor(() => expect(controller.notifications.length).toBe(2));

    await controller.markAsRead("read-1");

    expect(api.updateDocument).not.toHaveBeenCalled();
  });

  it("does nothing for a row the feed has not loaded", async () => {
    const controller = mount();
    await vi.waitFor(() => expect(controller.notifications.length).toBe(2));

    await controller.markAsRead("elsewhere");

    expect(api.updateDocument).not.toHaveBeenCalled();
  });
});
