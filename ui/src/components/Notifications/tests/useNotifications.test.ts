// Mark-as-read goes to the dotted method, which needs only the name.
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

const MARK_AS_READ =
  "frappe.desk.doctype.notification_log.notification_log.mark_as_read";

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
  it("calls the dotted method with the docname", async () => {
    const controller = mount();
    await vi.waitFor(() => expect(controller.notifications.length).toBe(2));

    await controller.markAsRead("unread-1");

    expect(api.runMethod).toHaveBeenCalledWith(MARK_AS_READ, {
      docname: "unread-1",
    });
    expect(api.updateDocument).not.toHaveBeenCalled();
  });

  it("sends the request for a name the feed has not loaded", async () => {
    const controller = mount();
    await vi.waitFor(() => expect(controller.notifications.length).toBe(2));

    await controller.markAsRead("elsewhere");

    expect(api.runMethod).toHaveBeenCalledWith(MARK_AS_READ, {
      docname: "elsewhere",
    });
  });

  it("refreshes the unread count afterwards", async () => {
    const controller = mount();
    await vi.waitFor(() => expect(controller.notifications.length).toBe(2));
    const before = api.countDocuments.mock.calls.length;

    await controller.markAsRead("unread-1");

    await vi.waitFor(() =>
      expect(api.countDocuments.mock.calls.length).toBeGreaterThan(before)
    );
  });

  it("drops the unread count optimistically for a loaded unread row", async () => {
    const controller = mount();
    await vi.waitFor(() => expect(controller.unreadCount).toBe(1));

    void controller.markAsRead("unread-1");

    expect(controller.unreadCount).toBe(0);
  });
});
