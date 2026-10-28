import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { afterAll, afterEach, describe, expect, it, vi } from "vitest";
import contributions, { discover, report } from "../contributions.js";

const RESOLVED_ID = "\0virtual:frappe/contributions";
const PAGE = "export default { component: () => null }";
const roots: string[] = [];

type Replacement = { app: string; key: string; page: string };

/** Writes each app's files under a fresh folder and returns the manifest for it. */
function bench(apps: Record<string, Record<string, string>>) {
  const root = mkdtempSync(join(tmpdir(), "contributions-"));
  roots.push(root);
  return Object.entries(apps).map(([app, tree]) => {
    const source_dir = join(root, app, app);
    for (const [path, content] of Object.entries(tree)) {
      mkdirSync(dirname(join(source_dir, path)), { recursive: true });
      writeFileSync(join(source_dir, path), content);
    }
    return { app, source_dir };
  });
}

const TICKET = "support/doctype/hd_ticket";
const ticketDefinition = {
  [`${TICKET}/hd_ticket.json`]: JSON.stringify({ name: "HD Ticket" }),
};

/** The helpdesk app owning HD Ticket, with `pages.json` holding `declaration`. */
function owner(declaration: unknown, extra: Record<string, string> = {}) {
  return {
    ...ticketDefinition,
    [`${TICKET}/frontend/record.js`]: "export default {}",
    [`${TICKET}/frontend/pages/runner.js`]: PAGE,
    [`${TICKET}/frontend/pages.json`]:
      typeof declaration === "string"
        ? declaration
        : JSON.stringify(declaration),
    ...extra,
  };
}

afterAll(() => {
  for (const root of roots) rmSync(root, { recursive: true, force: true });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("a replacement page its owner declares", () => {
  it("resolves the key to the page file, under the doctype's real name", () => {
    const manifest = bench({ helpdesk: owner({ record: "runner" }) });
    const { replacements, warnings } = discover(manifest);

    expect(replacements).toEqual([
      {
        app: "helpdesk",
        doctype: "HD Ticket",
        key: "record",
        page: "runner",
        foreign: false,
        file: join(manifest[0].source_dir, TICKET, "frontend/pages/runner.js"),
      },
    ]);
    expect(warnings).toEqual([]);
  });

  it("gives a page that pages.json does not name no address and no warning", () => {
    const manifest = bench({
      helpdesk: owner(
        { record: "runner" },
        { [`${TICKET}/frontend/pages/spare.js`]: PAGE },
      ),
    });
    const { replacements, warnings } = discover(manifest);

    expect(replacements.map((entry: Replacement) => entry.page)).toEqual([
      "runner",
    ]);
    expect(warnings).toEqual([]);
  });

  it("declares nothing without a pages.json", () => {
    const manifest = bench({
      helpdesk: {
        ...ticketDefinition,
        [`${TICKET}/frontend/pages/runner.js`]: PAGE,
      },
    });
    expect(discover(manifest).replacements).toEqual([]);
  });
});

describe("a replacement page declared under custom/", () => {
  it("is foreign and names the doctype from the owning app's JSON", () => {
    const manifest = bench({
      helpdesk: ticketDefinition,
      crm: {
        "fcrm/custom/hd_ticket/pages/inbox.js": PAGE,
        "fcrm/custom/hd_ticket/pages.json": JSON.stringify({ list: "inbox" }),
      },
    });
    const { replacements, warnings } = discover(
      manifest.slice(1),
      manifest.map((entry) => entry.source_dir),
    );

    expect(replacements).toEqual([
      {
        app: "crm",
        doctype: "HD Ticket",
        key: "list",
        page: "inbox",
        foreign: true,
        file: join(
          manifest[1].source_dir,
          "fcrm/custom/hd_ticket/pages/inbox.js",
        ),
      },
    ]);
    expect(warnings).toEqual([]);
  });
});

describe("a pages.json that cannot be read", () => {
  it("is ignored whole when it is not valid JSON", () => {
    const manifest = bench({ helpdesk: owner("{ record: runner") });
    const { replacements, warnings } = discover(manifest);

    expect(replacements).toEqual([]);
    expect(warnings).toEqual([
      `[frappe] ${join(manifest[0].source_dir, TICKET, "frontend/pages.json")} is not valid JSON; the whole file is ignored.`,
    ]);
  });

  it("is ignored whole when it is not a JSON object", () => {
    const manifest = bench({ helpdesk: owner(["runner"]) });
    const { replacements, warnings } = discover(manifest);

    expect(replacements).toEqual([]);
    expect(warnings).toEqual([
      `[frappe] ${join(manifest[0].source_dir, TICKET, "frontend/pages.json")} is not a JSON object; the whole file is ignored.`,
    ]);
  });
});

describe("a pages.json key that cannot be used", () => {
  const path = (manifest: { source_dir: string }[]) =>
    join(manifest[0].source_dir, TICKET, "frontend/pages.json");

  it("drops an unknown key and keeps the others", () => {
    const manifest = bench({
      helpdesk: owner({ record: "runner", form: "runner" }),
    });
    const { replacements, warnings } = discover(manifest);

    expect(replacements.map((entry: Replacement) => entry.key)).toEqual([
      "record",
    ]);
    expect(warnings).toEqual([
      `[frappe] ${path(manifest)}: unknown key "form", only "record" and "list" are read; that key is ignored.`,
    ]);
  });

  it("drops a key that names no file in pages/", () => {
    const manifest = bench({ helpdesk: owner({ record: "missing" }) });
    const { replacements, warnings } = discover(manifest);

    expect(replacements).toEqual([]);
    expect(warnings).toEqual([
      `[frappe] ${path(manifest)}: "record" names "missing", but there is no pages/missing.js; that key is ignored.`,
    ]);
  });

  it("drops a key whose value is not a string", () => {
    const manifest = bench({ helpdesk: owner({ record: 3 }) });
    const { replacements, warnings } = discover(manifest);

    expect(replacements).toEqual([]);
    expect(warnings).toEqual([
      `[frappe] ${path(manifest)}: "record" is not a page name, a { "page", "apps" } entry or a list of entries; that key is ignored.`,
    ]);
  });

  it("drops a key that names a reserved page, even when the file exists", () => {
    const manifest = bench({
      helpdesk: owner(
        { list: "record" },
        { [`${TICKET}/frontend/pages/record.js`]: PAGE },
      ),
    });
    const { replacements, warnings } = discover(manifest);

    expect(replacements).toEqual([]);
    expect(warnings).toEqual([
      `[frappe] ${path(manifest)}: "list" names "record", a name reserved for the standard pages; that key is ignored.`,
    ]);
  });
});

describe("a pages.json entry that names apps", () => {
  const path = (manifest: { source_dir: string }[]) =>
    join(manifest[0].source_dir, TICKET, "frontend/pages.json");
  const scoped = (declaration: unknown, extra: Record<string, string> = {}) =>
    bench({
      helpdesk: owner(declaration, {
        [`${TICKET}/frontend/pages/card.js`]: PAGE,
        ...extra,
      }),
      crm: {},
      frappe: {},
    });
  const found = (replacements: (Replacement & { apps?: string[] })[]) =>
    replacements.map(({ key, page, apps }) => ({ key, page, apps }));

  it("carries the apps of one object, and an array's entry with no apps applies in every app", () => {
    const manifest = scoped({
      record: { page: "runner", apps: ["crm"] },
      list: [{ page: "runner", apps: ["frappe", "helpdesk"] }, { page: "card" }],
    });
    const { replacements, warnings } = discover(manifest);

    expect(found(replacements)).toEqual([
      { key: "record", page: "runner", apps: ["crm"] },
      { key: "list", page: "runner", apps: ["frappe", "helpdesk"] },
      { key: "list", page: "card", apps: undefined },
    ]);
    expect(warnings).toEqual([]);
  });

  it("emits the apps of a scoped entry only", () => {
    const manifest = scoped({
      list: [{ page: "runner", apps: ["crm"] }, { page: "card" }],
    });
    const code = load(contributions(manifest));

    expect(code).toContain(`key: "list", apps: ["crm"], foreign: false, title: r0?.title`);
    expect(code).toContain(`key: "list", foreign: false, title: r1?.title`);
  });

  it("drops an app that is not on the bench from its entry, and keeps the others", () => {
    const manifest = scoped({ record: { page: "runner", apps: ["crm", "hrms"] } });
    const { replacements, warnings } = discover(manifest);

    expect(found(replacements)).toEqual([
      { key: "record", page: "runner", apps: ["crm"] },
    ]);
    expect(warnings).toEqual([
      `[frappe] ${path(manifest)}: "record" names app "hrms" for "runner", but it is not on the bench; it is dropped from that entry.`,
    ]);
  });

  it("drops an entry left with no app on the bench, never widening it to every app", () => {
    const manifest = scoped({
      record: [{ page: "runner", apps: ["hrms"] }, { page: "card", apps: [] }],
    });
    const { replacements, warnings } = discover(manifest);

    expect(replacements).toEqual([]);
    expect(warnings).toEqual([
      `[frappe] ${path(manifest)}: "record" names app "hrms" for "runner", but it is not on the bench; it is dropped from that entry.`,
      `[frappe] ${path(manifest)}: "record" gives "runner" no app on the bench, and "apps" never means every app; that entry is ignored.`,
      `[frappe] ${path(manifest)}: "record" gives "card" no app on the bench, and "apps" never means every app; that entry is ignored.`,
    ]);
  });

  it("warns about no app that is on the bench but not in the bundle", () => {
    const manifest = scoped({ record: { page: "runner", apps: ["crm"] } });
    const { replacements, warnings } = discover(
      manifest.slice(0, 1),
      manifest.map((entry) => entry.source_dir),
    );

    expect(found(replacements)).toEqual([
      { key: "record", page: "runner", apps: ["crm"] },
    ]);
    expect(warnings).toEqual([]);
  });

  it.each([
    [
      "names one app in two entries",
      [
        { page: "runner", apps: ["crm"] },
        { page: "card", apps: ["frappe", "crm"] },
      ],
      `"record" names app "crm" in more than one entry`,
    ],
    [
      "has two entries with no apps",
      [{ page: "runner" }, { page: "card" }],
      `"record" has more than one entry with no "apps"`,
    ],
    [
      "has an entry with an unknown field",
      { page: "runner", app: ["crm"] },
      `"record" has an entry with the unknown field "app"`,
    ],
    [
      "has an entry with no page",
      [{ apps: ["crm"] }],
      `"record" has an entry with no page name`,
    ],
    [
      "gives apps that are not a list of names",
      { page: "runner", apps: "crm" },
      `"record" gives "runner" an "apps" that is not a list of app names`,
    ],
    [
      "lists a bare page name",
      ["runner"],
      `"record" is not a page name, a { "page", "apps" } entry or a list of entries`,
    ],
    ["is an empty list", [], `"record" is an empty list`],
    [
      "has an entry naming no file in pages/",
      [{ page: "runner", apps: ["crm"] }, { page: "missing" }],
      `"record" names "missing", but there is no pages/missing.js`,
    ],
  ])("drops a key that %s", (_, record, problem) => {
    const manifest = scoped({ record, list: "card" });
    const { replacements, warnings } = discover(manifest);

    expect(found(replacements)).toEqual([
      { key: "list", page: "card", apps: undefined },
    ]);
    expect(warnings).toEqual([
      `[frappe] ${path(manifest)}: ${problem}; that key is ignored.`,
    ]);
  });
});

describe("a .js file beside pages/", () => {
  it("is a reserved handler file in the owner's frontend/ when the page exists", () => {
    const manifest = bench({
      helpdesk: owner(
        { record: "runner" },
        {
          [`${TICKET}/frontend/list.js`]: "export default {}",
          [`${TICKET}/frontend/runner.js`]: "export default {}",
          [`${TICKET}/frontend/helpers.js`]: "export const x = 1",
        },
      ),
    });
    const { replacements, warnings } = discover(manifest);
    const handler = join(manifest[0].source_dir, TICKET, "frontend/runner.js");

    expect(replacements).toHaveLength(1);
    expect(warnings).toEqual([
      `[frappe] ${handler} is reserved for the handlers of pages/runner.js; it is ignored.`,
    ]);
  });

  it("is a reserved handler file under custom/ when the page exists", () => {
    const manifest = bench({
      crm: {
        "fcrm/custom/hd_ticket/record.js": "export default {}",
        "fcrm/custom/hd_ticket/inbox.js": "export default {}",
        "fcrm/custom/hd_ticket/pages/inbox.js": PAGE,
      },
    });
    const handler = join(
      manifest[0].source_dir,
      "fcrm/custom/hd_ticket/inbox.js",
    );

    expect(discover(manifest).warnings).toEqual([
      `[frappe] ${handler} is reserved for the handlers of pages/inbox.js; it is ignored.`,
    ]);
  });

  it("is a stray under custom/ when no page has its name", () => {
    const manifest = bench({
      crm: {
        "fcrm/custom/hd_ticket/record.js": "export default {}",
        "fcrm/custom/hd_ticket/list.js": "export default {}",
        "fcrm/custom/hd_ticket/inbox.js": "export default {}",
      },
    });
    const stray = join(
      manifest[0].source_dir,
      "fcrm/custom/hd_ticket/inbox.js",
    );

    expect(discover(manifest).warnings).toEqual([
      `[frappe] ${stray} has no pages/inbox.js beside it; it is ignored.`,
    ]);
  });
});

describe("one doctype's page replaced by two apps", () => {
  const clashing = () =>
    bench({
      helpdesk: owner({ record: "runner" }),
      crm: {
        "fcrm/custom/hd_ticket/pages/desk.js": PAGE,
        "fcrm/custom/hd_ticket/pages.json": JSON.stringify({
          record: "desk",
          list: "desk",
        }),
      },
    });

  it("keeps both and warns once, naming both apps", () => {
    const manifest = clashing();
    const { replacements, warnings } = discover(manifest);
    const [helpdesk, crm] = manifest.map((entry) => entry.source_dir);

    expect(
      replacements.map((entry: Replacement) => [entry.app, entry.key]),
    ).toEqual([
      ["helpdesk", "record"],
      ["crm", "record"],
      ["crm", "list"],
    ]);
    expect(warnings).toEqual([
      `[frappe] HD Ticket's record page is replaced by more than one app: ` +
        `helpdesk (${join(helpdesk, TICKET, "frontend/pages/runner.js")}), ` +
        `crm (${join(crm, "fcrm/custom/hd_ticket/pages/desk.js")}). ` +
        `The owner's comes first, then custom/ ones in the site's app order, ` +
        `and the last one wins at runtime.`,
    ]);
  });
});

describe("one doctype's page replaced by two apps, per app", () => {
  const twoApps = (helpdesk: unknown, crm: unknown) =>
    bench({
      helpdesk: owner(helpdesk),
      crm: {
        "fcrm/custom/hd_ticket/pages/desk.js": PAGE,
        "fcrm/custom/hd_ticket/pages.json": JSON.stringify(crm),
      },
      frappe: {},
    });

  it("warns about two entries that name one app, naming that app", () => {
    const manifest = twoApps(
      { record: { page: "runner", apps: ["frappe", "crm"] } },
      { record: { page: "desk", apps: ["crm"] } },
    );
    const { warnings } = discover(manifest);
    const [helpdesk, crm] = manifest.map((entry) => entry.source_dir);

    expect(warnings).toEqual([
      `[frappe] HD Ticket's record page in crm is replaced by more than one app: ` +
        `helpdesk (${join(helpdesk, TICKET, "frontend/pages/runner.js")}), ` +
        `crm (${join(crm, "fcrm/custom/hd_ticket/pages/desk.js")}). ` +
        `The owner's comes first, then custom/ ones in the site's app order, ` +
        `and the last one wins at runtime.`,
    ]);
  });

  it.each([
    ["an entry that names an app and one that names none", { record: "runner" }],
    ["entries that name different apps", { record: { page: "runner", apps: ["frappe"] } }],
  ])("warns about nothing for %s", (_, helpdesk) => {
    const manifest = twoApps(helpdesk, { record: { page: "desk", apps: ["crm"] } });

    expect(discover(manifest).warnings).toEqual([]);
  });
});

/** Runs the plugin's `load` with the one context method it calls. */
function load(plugin: any, watched: string[] = []) {
  return plugin.load.call(
    { addWatchFile: (file: string) => watched.push(file) },
    RESOLVED_ID,
  );
}

describe("the generated module", () => {
  it("imports each replacement and drops one with no component at runtime", () => {
    const manifest = bench({ helpdesk: owner({ record: "runner" }) });
    const plugin = contributions(manifest) as any;
    const file = join(
      manifest[0].source_dir,
      TICKET,
      "frontend/pages/runner.js",
    );

    expect(plugin.resolveId("virtual:frappe/contributions")).toBe(RESOLVED_ID);
    const code = load(plugin);
    expect(code).toContain(`import r0 from ${JSON.stringify(file)}`);
    expect(code).toContain(
      `  replacements: [\n` +
        `    { app: "helpdesk", doctype: "HD Ticket", key: "record", foreign: false, ` +
        `title: r0?.title, component: r0?.component, handlers: r0?.component, ` +
        `__file: ${JSON.stringify(file)} },\n` +
        `  ].filter(usable),`,
    );
  });

  it("watches each pages.json, so an edit reloads the module in dev", () => {
    const manifest = bench({ helpdesk: owner({ record: "runner" }) });
    const watched: string[] = [];

    load(contributions(manifest), watched);

    expect(watched).toEqual([
      join(manifest[0].source_dir, TICKET, "frontend/pages.json"),
    ]);
  });
});

describe("the terminal output", () => {
  const withWarning = () => bench({ helpdesk: owner({ form: "runner" }) });

  it("prints each warning once through vite's logger, and still replays it in the browser", () => {
    const manifest = withWarning();
    const plugin = contributions(manifest) as any;
    const logger = { warn: vi.fn() };
    plugin.configResolved({ logger });

    const code = load(plugin);
    const [warning] = discover(manifest).warnings;

    expect(logger.warn.mock.calls).toEqual([[warning]]);
    expect(code).toContain(`console.warn(${JSON.stringify(warning)})`);
  });

  it("falls back to console.warn when no config was resolved", () => {
    const manifest = withWarning();
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});

    load(contributions(manifest));

    expect(warn).toHaveBeenCalledTimes(1);
    expect(warn.mock.calls[0][0]).toMatch(/^\[frappe\] .*unknown key "form"/);
  });

  it("prints nothing when discovery found nothing wrong", () => {
    const logger = { warn: vi.fn() };
    report([], logger);
    expect(logger.warn).not.toHaveBeenCalled();
  });
});

describe("a page whose slug is already taken on the bench", () => {
  const erpnext = {
    "modules.txt": "Selling\nAccounts\n",
    "selling/doctype/lead/lead.json": JSON.stringify({ name: "Lead" }),
    "selling/doctype/lead_item/lead_item.json": JSON.stringify({
      name: "Lead Item",
      istable: 1,
    }),
  };

  it("warns about a flat app's page that a doctype's slug holds, and keeps the page", () => {
    const [crm, other] = bench({
      crm: {
        "fcrm/frontend/pages/lead.js": PAGE,
        "fcrm/frontend/pages/selling.js": PAGE,
        "fcrm/frontend/pages/lead-item.js": PAGE,
      },
      erpnext,
    });
    const { pages, pageWarnings } = discover([crm], [crm.source_dir, other.source_dir]);

    expect(pages.map((page) => page.slug).sort()).toEqual(["lead", "lead-item", "selling"]);
    expect(pageWarnings).toEqual([
      `[frappe] ${join(crm.source_dir, "fcrm/frontend/pages/lead.js")}: the doctype 'Lead' ` +
        "has the address /lead; on a site that has it, the page gets no route.",
    ]);
  });

  it("warns about a modular app's page that a module's slug holds", () => {
    const [crm, other] = bench({
      crm: {
        "fcrm/frontend/pages/lead.js": PAGE,
        "fcrm/frontend/pages/accounts.js": PAGE,
      },
      erpnext,
    });
    const manifest = [{ ...crm, modular: true }];
    const { pageWarnings } = discover(manifest, [crm.source_dir, other.source_dir]);

    expect(pageWarnings).toEqual([
      `[frappe] ${join(crm.source_dir, "fcrm/frontend/pages/accounts.js")}: the module ` +
        "'Accounts' has the address /accounts; on a site that has it, the page gets no route.",
    ]);
  });

  it("warns once, with both paths, about two pages of one app with one slug", () => {
    const [crm] = bench({
      crm: {
        "fcrm/frontend/pages/deals.js": PAGE,
        "sales/frontend/pages/deals.js": PAGE,
      },
    });
    const [helpdesk] = bench({ helpdesk: { "desk/frontend/pages/deals.js": PAGE } });
    const { pageWarnings } = discover([crm, helpdesk]);

    expect(pageWarnings).toEqual([
      "[frappe] 'crm' ships more than one page named 'deals': " +
        `${join(crm.source_dir, "fcrm/frontend/pages/deals.js")}, ` +
        `${join(crm.source_dir, "sales/frontend/pages/deals.js")}. None of them gets a route.`,
    ]);
  });

  it("prints in the terminal only, since the router reports the clashes a site has", () => {
    const [crm, other] = bench({ crm: { "fcrm/frontend/pages/lead.js": PAGE }, erpnext });
    const plugin = contributions([crm], [crm.source_dir, other.source_dir]) as any;
    const logger = { warn: vi.fn() };
    plugin.configResolved({ logger });

    const code = load(plugin);
    const [warning] = discover([crm], [crm.source_dir, other.source_dir]).pageWarnings;

    expect(logger.warn.mock.calls).toEqual([[warning]]);
    expect(code).not.toContain("console.warn(\"[frappe]");
  });
});

describe("a settings component", () => {
  const SETTINGS = "export default {}";

  it("is found under <module>/frontend/settings/ by its file name", () => {
    const [crm] = bench({
      crm: {
        "fcrm/frontend/settings/telephony.vue": SETTINGS,
        "fcrm/frontend/settings/notes.txt": "",
      },
    });

    expect(discover([crm]).settings).toEqual([
      {
        app: "crm",
        name: "telephony",
        file: join(crm.source_dir, "fcrm/frontend/settings/telephony.vue"),
      },
    ]);
  });

  it("is imported lazily, so its chunk loads only when its pane opens", () => {
    const [crm] = bench({ crm: { "fcrm/frontend/settings/telephony.vue": SETTINGS } });
    const file = join(crm.source_dir, "fcrm/frontend/settings/telephony.vue");

    const code = load(contributions([crm]));

    expect(code).toContain(
      `  settings: [\n` +
        `    { app: "crm", name: "telephony", component: () => import(${JSON.stringify(file)}) },\n` +
        `  ],`,
    );
    expect(code).not.toMatch(/^import .*telephony\.vue/m);
  });

  it("keeps one name per app, and drops a name two modules of one app ship", () => {
    const [crm, helpdesk] = bench({
      crm: {
        "fcrm/frontend/settings/general.vue": SETTINGS,
        "sales/frontend/settings/general.vue": SETTINGS,
      },
      helpdesk: { "desk/frontend/settings/general.vue": SETTINGS },
    });
    const { settings, warnings } = discover([crm, helpdesk]);

    expect(settings.map((entry: { app: string }) => entry.app)).toEqual(["helpdesk"]);
    expect(warnings).toEqual([
      "[frappe] 'crm' ships more than one settings component named 'general': " +
        `${join(crm.source_dir, "fcrm/frontend/settings/general.vue")}, ` +
        `${join(crm.source_dir, "sales/frontend/settings/general.vue")}. None of them is used.`,
    ]);
  });
});

describe("an app's acts", () => {
  const ACTS = "export default []";

  it("are found at <module>/frontend/acts.js, one file per module", () => {
    const [crm] = bench({
      crm: {
        "fcrm/frontend/acts.js": ACTS,
        "telephony/frontend/acts.js": ACTS,
        "fcrm/doctype/crm_deal/frontend/acts.js": ACTS,
      },
    });

    expect(discover([crm]).acts).toEqual([
      { app: "crm", file: join(crm.source_dir, "fcrm/frontend/acts.js") },
      { app: "crm", file: join(crm.source_dir, "telephony/frontend/acts.js") },
    ]);
  });

  it("are imported lazily, so the cold load carries none of their code", () => {
    const [crm] = bench({ crm: { "fcrm/frontend/acts.js": ACTS } });
    const file = join(crm.source_dir, "fcrm/frontend/acts.js");

    const code = load(contributions([crm]));

    expect(code).toContain(
      `  acts: [\n` + `    { app: "crm", load: () => import(${JSON.stringify(file)}) },\n` + `  ],`,
    );
    expect(code).not.toMatch(/^import .*acts\.js/m);
  });
});
