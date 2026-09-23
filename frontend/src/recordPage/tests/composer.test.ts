// `page.composer` as executable claims: writers are a list like any surface, `open`
// lands the reader on a tab that draws the band, and `onPost` names the posted row.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

vi.mock("frappe-ui", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  dayjs: vi.fn(),
}));
vi.mock("@framework/ui/api", () => ({
  runMethod: vi.fn(async () => ({ data: null })),
}));

import { isComposerTab } from "../composer";
import { withRegisteringSource } from "../context";
import { createRecordPage, RECORD_PAGE_EVENTS, type RecordPageHost } from "../createRecordPage";
import { registerRecordPage, resetRegistry } from "../registry";
import {
  TAB_ITEM_KEYS,
  type PostedRow,
  type RecordPageApi,
  type TabItem,
  type WriterItem,
} from "../types";

const Body = { render: () => null };

const TABS: TabItem[] = [
  { name: "activity", label: "Activity" },
  { name: "emails", label: "Emails" },
  { name: "files", label: "Files" },
  { name: "details", label: "Details" },
];

const COMMENT: WriterItem = {
  name: "comment",
  label: "Comment",
  icon: "lucide-message-square",
};

/** The host's composer half, recorded, not performed. */
function makePage(start = "details") {
  const current = ref(start);
  const writer = ref("");
  const opened: [string, unknown][] = [];
  const activated: string[] = [];
  const host: RecordPageHost = {
    doctype: "CRM Deal",
    docname: "CRM-DEAL-1",
    doc: ref({}),
    saved: ref({}),
    meta: ref(null),
    perms: () => ({}),
    isDirty: () => false,
    activeTab: () => current.value,
    activateTab: (name) => {
      activated.push(name);
      current.value = name;
    },
    save: async () => {},
    reload: async () => {},
    router: {} as any,
    activityRows: () => [],
    scrollToActivity: async () => true,
    reloadActivity: async () => {},
    fileRows: () => [],
    reloadFiles: async () => {},
    openWriter: (name, options) => {
      opened.push([name, options]);
      writer.value = name;
    },
    closeWriter: () => void (writer.value = ""),
    activeWriter: () => writer.value,
  };
  const controller = createRecordPage(host);
  controller.tabs.provideBuiltins(() => TABS);
  controller.composer.provideBuiltins(() => [COMMENT]);
  return { controller, page: controller.page, opened, activated, current };
}

let warnings: string[];

beforeEach(() => {
  resetRegistry();
  warnings = [];
  vi.spyOn(console, "warn").mockImplementation((message: string) => void warnings.push(message));
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("the writers a script reads and adds", () => {
  it("adds a scripted writer beside the built-in comment", async () => {
    const { controller, page } = makePage();
    registerRecordPage("CRM Deal", {
      onRefresh: (page) =>
        page.composer.add({
          name: "call",
          label: "Log a call",
          component: Body,
        }),
    });
    await controller.refresh();

    expect(page.composer.has("comment")).toBe(true);
    expect(page.composer.has("call")).toBe(true);
    expect(controller.composer.visible().map((item) => item.name)).toEqual(["comment", "call"]);
  });

  it("drops a key the composer does not read", () => {
    const { controller } = makePage();
    controller.composer.add({
      name: "call",
      label: "Call",
      window: "floating",
    } as WriterItem);

    expect(controller.composer.find("call")).toEqual({
      name: "call",
      label: "Call",
    });
  });
});

describe("open", () => {
  it("moves the reader from details to activity, then asks the host to open the writer", () => {
    const { page, opened, activated } = makePage();
    page.composer.open("comment", { draft: { content: "hi" } });

    expect(activated).toEqual(["activity"]);
    expect(opened).toEqual([["comment", { draft: { content: "hi" } }]]);
  });

  it("stays on a script's tab that draws the band", async () => {
    const { controller, page, opened, activated, current } = makePage();
    registerRecordPage("CRM Deal", {
      onRefresh: (page) => page.tabs.add({ name: "calls", label: "Calls", composer: true }),
    });
    await controller.refresh();
    current.value = "calls";
    page.composer.open("comment");

    expect(activated).toEqual([]);
    expect(opened).toEqual([["comment", {}]]);
  });

  it("stays on emails, which draws the band", () => {
    const { page, activated } = makePage("emails");
    page.composer.open("comment");

    expect(activated).toEqual([]);
  });

  it("lands on the first tab that draws the band when activity is hidden", async () => {
    const { controller, page, activated } = makePage();
    registerRecordPage("CRM Deal", {
      onRefresh: (page) => page.tabs.hide("activity"),
    });
    await controller.refresh();
    page.composer.open("comment");

    expect(activated).toEqual(["emails"]);
  });

  it("warns and opens nothing for an unknown writer", () => {
    const { page, opened, activated } = makePage();
    page.composer.open("fax");

    expect(opened).toEqual([]);
    expect(activated).toEqual([]);
    expect(warnings.join("\n")).toContain('page.composer.open("fax") — no such writer');
  });

  it("warns and opens nothing for a hidden writer", async () => {
    const { controller, page, opened } = makePage();
    registerRecordPage("CRM Deal", {
      onRefresh: (page) => page.composer.hide("comment"),
    });
    await controller.refresh();
    page.composer.open("comment");

    expect(opened).toEqual([]);
    expect(warnings.join("\n")).toContain("it is hidden");
  });

  it("warns and opens nothing when no tab draws the band", async () => {
    const { controller, page, opened } = makePage();
    registerRecordPage("CRM Deal", {
      onRefresh: (page) => {
        page.tabs.hide("activity");
        page.tabs.hide("emails");
      },
    });
    await controller.refresh();
    page.composer.open("comment");

    expect(opened).toEqual([]);
    expect(warnings.join("\n")).toContain("no tab on the strip draws the composer");
  });

  it("waits for the commit when called in a replay", async () => {
    const { controller, opened } = makePage();
    let seen: unknown[] = [];
    registerRecordPage("CRM Deal", {
      onRefresh: (page) => {
        page.composer.open("comment");
        seen = [...opened];
      },
    });
    await controller.refresh();

    expect(seen).toEqual([]);
    expect(opened).toEqual([["comment", {}]]);
  });
});

describe("active and close", () => {
  it("read and shut the writer through the host", () => {
    const { page } = makePage();
    expect(page.composer.active).toBe("");

    page.composer.open("comment");
    expect(page.composer.active).toBe("comment");

    page.composer.close();
    expect(page.composer.active).toBe("");
  });
});

describe("onPost", () => {
  it("fires for every source with the posted row's key", async () => {
    const { controller } = makePage();
    const calls: [string, unknown][] = [];
    for (const source of ["first", "second"])
      await withRegisteringSource(source, async () =>
        registerRecordPage("CRM Deal", {
          onPost: (_page, post) => void calls.push([source, post]),
        })
      );
    await controller.firePost("comment:c9");

    expect(calls).toEqual([
      ["first", { name: "comment:c9" }],
      ["second", { name: "comment:c9" }],
    ]);
  });

  it("takes a handler that types its argument as the posted row", async () => {
    const { controller } = makePage();
    const keys: string[] = [];
    await withRegisteringSource("typed", async () =>
      registerRecordPage("CRM Deal", {
        onPost: (_page: RecordPageApi, post: PostedRow) => void keys.push(post.name),
      })
    );
    await controller.firePost("comment:c10");
    expect(keys).toEqual(["comment:c10"]);
  });

  it("is an event, so a script that handles it is not warned about", () => {
    expect(RECORD_PAGE_EVENTS).toContain("onPost");
  });
});

describe("a tab that draws the band", () => {
  it("keeps `composer` as a tab key", () => {
    const { controller } = makePage();
    controller.tabs.add({ name: "calls", label: "Calls", composer: true });

    expect(TAB_ITEM_KEYS).toContain("composer");
    expect(controller.tabs.find("calls")?.composer).toBe(true);
  });

  it("is activity, emails, or a tab that says so", () => {
    expect(isComposerTab({ name: "activity", label: "" })).toBe(true);
    expect(isComposerTab({ name: "emails", label: "" })).toBe(true);
    expect(isComposerTab({ name: "files", label: "" })).toBe(false);
    expect(isComposerTab({ name: "calls", label: "", composer: true })).toBe(true);
  });
});
