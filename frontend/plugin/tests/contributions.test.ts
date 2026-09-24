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
      `[frappe] ${path(manifest)}: "record" is not a page name; that key is ignored.`,
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
    const code = plugin.load(RESOLVED_ID);
    expect(code).toContain(`import r0 from ${JSON.stringify(file)}`);
    expect(code).toContain(
      `  replacements: [\n` +
        `    { app: "helpdesk", doctype: "HD Ticket", key: "record", foreign: false, ` +
        `title: r0?.title, component: r0?.component, handlers: r0?.component, ` +
        `__file: ${JSON.stringify(file)} },\n` +
        `  ].filter(usable),`,
    );
  });
});

describe("the terminal output", () => {
  const withWarning = () => bench({ helpdesk: owner({ form: "runner" }) });

  it("prints each warning once through vite's logger, and still replays it in the browser", () => {
    const manifest = withWarning();
    const plugin = contributions(manifest) as any;
    const logger = { warn: vi.fn() };
    plugin.configResolved({ logger });

    const code = plugin.load(RESOLVED_ID);
    const [warning] = discover(manifest).warnings;

    expect(logger.warn.mock.calls).toEqual([[warning]]);
    expect(code).toContain(`console.warn(${JSON.stringify(warning)})`);
  });

  it("falls back to console.warn when no config was resolved", () => {
    const manifest = withWarning();
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});

    (contributions(manifest) as any).load(RESOLVED_ID);

    expect(warn).toHaveBeenCalledTimes(1);
    expect(warn.mock.calls[0][0]).toMatch(/^\[frappe\] .*unknown key "form"/);
  });

  it("prints nothing when discovery found nothing wrong", () => {
    const logger = { warn: vi.fn() };
    report([], logger);
    expect(logger.warn).not.toHaveBeenCalled();
  });
});
