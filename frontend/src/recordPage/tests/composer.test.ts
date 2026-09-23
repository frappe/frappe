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

import { resetSession, setSession } from "@framework/ui/composables/useSession";
import type { Session } from "@framework/ui/api";
import { composerHost } from "@/pages/record/composer/composerHost";
import { closeComposer, composerState, openComposer, preferredWindow } from "@/shell/composer";
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

/** The host's composer half, recorded, not performed, unless `composer` is the record page's own. */
function makePage(start = "details", composer: Partial<RecordPageHost> = {}) {
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
    ...composer,
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

describe("window", () => {
  let user = 0;

  beforeEach(() => {
    closeComposer();
    const session = { user: { name: `reader-${++user}` }, roles: [], lang: "en", timezone: "UTC" };
    setSession({ ...session, defaults: {} } as unknown as Session);
  });

  afterEach(() => {
    resetSession();
    localStorage.clear();
  });

  /** A page on the record page's own composer host, over the one store. */
  function onStore(docname = "CRM-DEAL-1") {
    return makePage("activity", composerHost("CRM Deal", docname)).page;
  }

  it("reads the reader's choice while no writer is open on this record", () => {
    const page = onStore();
    expect(page.composer.window).toBe("docked");

    page.composer.window = "floating";
    expect(page.composer.window).toBe("floating");
    expect(preferredWindow()).toBe("floating");
  });

  it("reads the open card's place while this record's writer is open", () => {
    const page = onStore();
    page.composer.open("comment", { window: "floating" });

    expect(page.composer.active).toBe("comment");
    expect(page.composer.window).toBe("floating");
    expect(preferredWindow()).toBe("docked");
  });

  it("moves the open card and keeps the choice", () => {
    const page = onStore();
    page.composer.open("comment");
    page.composer.window = "floating";

    expect(composerState.window).toBe("floating");
    expect(preferredWindow()).toBe("floating");
  });

  it("keeps the choice without moving another record's open card", () => {
    const page = onStore();
    openComposer("CRM Deal", "CRM-DEAL-2", "comment", undefined, "docked");
    page.composer.window = "floating";

    expect(composerState).toMatchObject({ name: "CRM-DEAL-2", window: "docked" });
    expect(preferredWindow()).toBe("floating");
    expect(page.composer.window).toBe("floating");
  });

  it("warns and changes nothing for a value other than the two", () => {
    const page = onStore();
    page.composer.open("comment");
    (page.composer as { window: string }).window = "minimized";

    expect(page.composer.window).toBe("docked");
    expect(preferredWindow()).toBe("docked");
    expect(warnings.join("\n")).toContain('page.composer.window = "minimized"');
  });

  it("hands an open's window to the host with the draft", () => {
    const { page, opened } = makePage();
    page.composer.open("comment", { draft: { content: "hi" }, window: "floating" });

    expect(opened).toEqual([["comment", { draft: { content: "hi" }, window: "floating" }]]);
  });

  it("keeps an open's window when the open waits for a replay", async () => {
    const { controller, opened } = makePage();
    registerRecordPage("CRM Deal", {
      onRefresh: (page) => page.composer.open("comment", { window: "floating" }),
    });
    await controller.refresh();

    expect(opened).toEqual([["comment", { window: "floating" }]]);
  });
});
