import { afterEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

// DOMPurify needs a real browser DOM, which the test DOM is not.
vi.mock("../../utils/sanitize", () => ({
  sanitizeHtml: vi.fn((html: string) =>
    html === "<b>Raw</b>" ? "cleaned" : html
  ),
}));

import { sanitizeHtml } from "../../utils/sanitize";
import { Notifications } from "../index";
import { mount, rows, unmountAll } from "./mount";

afterEach(unmountAll);

const logs = () => [
  {
    name: "a",
    title: "<b>Unread one</b>",
    read: 0,
    creation: "2026-01-01 10:00:00",
  },
  { name: "b", title: "Read one", read: 1, creation: "2026-01-01 09:00:00" },
];

const button = (root: HTMLElement, text: string) =>
  Array.from(root.querySelectorAll("button")).find(
    (el) =>
      el.textContent?.includes(text) || el.getAttribute("aria-label") === text
  );

describe("Notifications", () => {
  it("opens on Unread and shows only unread logs there", async () => {
    const root = await mount(Notifications, { notifications: logs() });

    expect(rows(root)).toHaveLength(1);
    expect(rows(root)[0].textContent).toContain("Unread one");
    expect(rows(root)[0].hasAttribute("data-unread")).toBe(true);
    expect(button(root, "Mark all as read")).toBeDefined();
  });

  it("shows read logs, and no Mark all as read, on the Read tab", async () => {
    const root = await mount(Notifications, {
      notifications: logs(),
      activeTab: "read",
    });

    expect(rows(root)).toHaveLength(1);
    expect(rows(root)[0].textContent).toContain("Read one");
    expect(rows(root)[0].hasAttribute("data-unread")).toBe(false);
    expect(button(root, "Mark all as read")).toBeUndefined();
  });

  it("emits select for a row and mark-as-read for its tick, never both", async () => {
    const events: string[] = [];
    const root = await mount(Notifications, {
      notifications: logs(),
      onSelect: (n: { name: string }) => events.push(`select ${n.name}`),
      "onMark-as-read": (n: { name: string }) => events.push(`read ${n.name}`),
    });

    button(root, "Mark as read")!.click();
    expect(events).toEqual(["read a"]);

    rows(root)[0].click();
    expect(events).toEqual(["read a", "select a"]);
  });

  it("renders a title only through the sanitiser", async () => {
    const root = await mount(Notifications, {
      notifications: [
        { name: "x", title: "<b>Raw</b>", read: 0, creation: "" },
      ],
    });

    expect(sanitizeHtml).toHaveBeenCalledWith("<b>Raw</b>");
    expect(rows(root)[0].textContent).toContain("cleaned");
    expect(rows(root)[0].textContent).not.toContain("Raw");
  });

  it("keeps Load more when the fetched page has nothing for the open tab", async () => {
    const loads: number[] = [];
    const root = await mount(Notifications, {
      notifications: [{ name: "b", title: "Read one", read: 1, creation: "" }],
      hasNextPage: true,
      "onLoad-more": () => loads.push(1),
    });

    expect(rows(root)).toHaveLength(0);
    expect(root.querySelector("[data-slot=notifications-empty]")).toBeNull();

    button(root, "Load more")!.click();
    expect(loads).toHaveLength(1);
  });

  it("shows the skeleton while the first load runs, then the empty state", async () => {
    const loading = await mount(Notifications, {
      notifications: [],
      loading: true,
    });
    expect(
      loading.querySelector("[data-slot=notifications-loading]")
    ).not.toBeNull();
    expect(loading.querySelector("[data-slot=notifications-empty]")).toBeNull();

    const done = await mount(Notifications, { notifications: [] });
    await nextTick();
    expect(
      done.querySelector("[data-slot=notifications-empty]")?.textContent
    ).toContain("You're caught up");
  });
});
