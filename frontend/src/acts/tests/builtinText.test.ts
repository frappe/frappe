// The built-in acts' text: every built-in act has a description, every palette option passes its act's
// `input`, and no act's name holds `__`. Each surface's acts are built from the same builders the page uses.
import { describe, expect, it, vi } from "vitest";
import { ref } from "vue";

vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ data: [] }))));
vi.mock("frappe-ui", () => ({ toast: { success: vi.fn(), error: vi.fn() }, frappeRequest: vi.fn() }));

import { loadText, TEXT_SURFACES } from "../actText";
import { checkValue } from "../schema/checkValue";
import type { ActEntry, ActItem } from "../dispatcher";
import { shellItems } from "@/shell/shellActs";
import { headerMenuBuiltins, quickActionBuiltins } from "@/pages/record/builtinActions";
import { docstatusItems } from "@/pages/record/docstatusActs";
import { amendItem } from "@/pages/record/amendAct";
import { postCommentItem } from "@/recordPage/commentAct";
import { recordTabBuiltins } from "@/pages/record/tabs/recordTabs";
import { editorEntries } from "@/pages/doctypeEditor/entries/editorEntries";
import { listEntries } from "@/pages/list/listActs";
import { bulkKeyEntries } from "@/pages/list/bulkKeys";
import { bulkBarParts } from "@/pages/list/bulkBarParts";
import { editorItems, settingsItems } from "@/pages/doctypeEditor/editorActs";
import { canvasItems, fieldItems } from "@/pages/doctypeEditor/canvasActs";
import { childFieldItems } from "@/pages/doctypeEditor/childActs";
import { customizeItems } from "@/pages/doctypeEditor/customizeActs";
import { dangerItems } from "@/pages/doctypeEditor/dangerActs";
import { layoutItems } from "@/pages/doctypeEditor/layoutActs";
import { recordEntries } from "@/recordPage/recordForm";

const noop = () => {};
// The editor's builders read their host only when an act's `when` or `run` does.
const editorHost: any = {
  canvas: () => ({ state: { modes: ["Design", "Customize"] } }),
  recordOptions: () => [],
};

function shell(): ActItem[] {
  const host: any = {
    boot: {},
    openAbout: noop,
    confirmLogout: noop,
    rail: { customize: noop, shareLink: () => "link", sidebarCollapsed: () => false, toggleSidebar: noop },
  };
  return shellItems(host, noop);
}

function header(): ActItem[] {
  const rights = { roles: ["System Manager"], developerMode: true, meta: { name: "ToDo" } as any };
  const menu = headerMenuBuiltins(
    { delete: 1 },
    { favourited: false, toggle: noop },
    {
      follow: { following: false, toggle: noop },
      assign: { assignees: [], assign: noop } as any,
      rename: true,
      duplicate: true,
      editorEntries: editorEntries("ToDo", rights),
      editLayout: { path: "/layout" },
    }
  );
  const meta: any = { is_submittable: 1 };
  const status = [0, 1].flatMap((docstatus) =>
    docstatusItems({ meta, saved: { docstatus }, dirty: false, canWrite: true }, async () => {})
  );
  // `favourite` and `save` are drawn in pages/Record.vue; `new` and `favourite` in pages/list/listHeader.ts.
  const own = ["favourite", "save", "new"].map((name) => ({ name, run: noop }));
  return [...menu, ...status, amendItem(null), ...own] as ActItem[];
}

function quickActions(): ActItem[] {
  const attach = { name: "attach_file", run: noop, right: "write" } as any;
  return quickActionBuiltins({ email: 1, print: 1, write: 1 }, false, { following: false, toggle: noop }, attach);
}

function tabs(): ActItem[] {
  return recordTabBuiltins({ requestUpload: noop }).flatMap((tab) => (tab.create?.name ? [tab.create] : [])) as ActItem[];
}

function list(): ActItem[] {
  const host: any = {
    customizing: () => false,
    editorEntries: () => editorEntries("ToDo", { roles: ["System Manager"], developerMode: true, meta: { name: "ToDo" } as any }),
    starsLoaded: () => true,
    favourited: () => false,
  };
  const keys = bulkKeyEntries({
    selection: ref([]),
    cursor: ref(null),
    shown: () => true,
    locked: false,
    hasMenu: () => true,
    menuOpen: ref(false),
    toggle: noop,
    extendTo: noop,
  });
  return [...listEntries(host, []), ...keys].map((entry: ActEntry) => entry.item);
}

function bulk(): ActItem[] {
  const scope: any = { selected: () => ({}), count: ref(0), all: ref(false), approx: ref(false) };
  const options: any = {
    host: { lists: { bulkActions: { resolve: () => [] } } },
    doctype: "ToDo",
    meta: ref({ is_submittable: 1 }),
    selection: ref([]),
    scope,
    reload: noop,
    askDelete: noop,
  };
  const boot: any = { session: { user: { name: "test@example.com" } } };
  return bulkBarParts(options, boot, {} as any).builtins() as ActItem[];
}

const BUILT: Record<string, () => ActItem[]> = {
  shell,
  header,
  quickActions,
  tabs,
  list: () => [...list(), ...bulk()],
  // The delete card act is drawn in pages/cards/CardsView.vue.
  cards: () => [{ name: "delete_card", run: noop }],
  editor: () => editorItems(editorHost),
  canvas: () => canvasItems(editorHost),
  fields: () => [...fieldItems(editorHost), ...childFieldItems(editorHost)],
  settings: () => settingsItems(editorHost),
  customize: () => customizeItems(editorHost),
  danger: () => dangerItems(editorHost),
  layouts: () => layoutItems(editorHost),
  // The entries read their host only when an act runs.
  record: () => [postCommentItem(async () => ""), ...recordEntries({} as any).map((entry) => entry.item)],
};

describe("the built-in acts' text", () => {
  it("covers every surface that has a sidecar", () => {
    expect(Object.keys(BUILT).sort()).toEqual([...TEXT_SURFACES].sort());
  });

  describe.each(Object.keys(BUILT))("%s", (surface) => {
    it("describes every act it draws, and only those", async () => {
      const drawn = BUILT[surface]().filter((item) => typeof item.run === "function");
      const text = await loadText(surface);
      const names = drawn.map((item) => item.name);
      expect(names.filter((name) => !text[name]?.description)).toEqual([]);
      expect(Object.keys(text).filter((name) => !names.includes(name))).toEqual([]);
    });

    it("names no act with `__`", () => {
      expect(BUILT[surface]().filter((item) => item.name.includes("__"))).toEqual([]);
    });

    it("gives every palette option a value its act's input accepts", async () => {
      const text = await loadText(surface);
      for (const item of BUILT[surface]().filter((one) => one.argument)) {
        const options = item.argument!.options(editorHost, "");
        // Options that read the server answer with a promise; the dispatcher test covers those.
        if (!Array.isArray(options)) {
          options.catch(noop);
          continue;
        }
        for (const option of options) expect(checkValue(item.input ?? text[item.name].input!, option.value)).toBeUndefined();
      }
    });
  });
});
