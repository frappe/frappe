import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { computed, effectScope, type EffectScope } from "vue";
import { updateDocument } from "../../../api";
import {
  clearDataCache,
  feedFieldRead,
  readCachedDocument,
  readCachedList,
  takeTicket,
} from "../../../cache";
import {
  resolveFieldCurrency,
  setDocValueReader,
  resetDocValueReader,
  getDocValueReader,
  useDocValueReader,
} from "../resolveCurrency";

const OLD = "2026-09-01 10:00:00.000000";
const NEW = "2026-09-03 10:00:00.000000";

const fetchMock = vi.fn<typeof fetch>();

function respond(body: unknown, status = 200) {
  fetchMock.mockImplementationOnce(async () => new Response(JSON.stringify(body), { status }));
}

/** The next request waits until the returned function answers it. */
function respondLater(): (body: unknown, status?: number) => void {
  let answer!: (response: Response) => void;
  fetchMock.mockImplementationOnce(() => new Promise((resolve) => (answer = resolve)));
  return (body, status = 200) => answer(new Response(JSON.stringify(body), { status }));
}

function acme(currency: string, modified = OLD) {
  return { name: "Acme", modified, default_currency: currency };
}

/** Lets a reply's promise hops run. */
const flush = () => new Promise((resolve) => setTimeout(resolve));

beforeEach(() => {
  clearDataCache();
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockReset();
});

afterEach(() => {
  resetDocValueReader();
  vi.unstubAllGlobals();
});

describe("resolveFieldCurrency", () => {
  // 1. No options → site default.
  it("falls back to the default currency when there are no options", () => {
    expect(resolveFieldCurrency(undefined, { defaultCurrency: "USD" })).toBe(
      "USD"
    );
    expect(resolveFieldCurrency("", { defaultCurrency: "USD" })).toBe("USD");
  });

  it("returns undefined when nothing resolves and there is no default", () => {
    expect(resolveFieldCurrency(undefined)).toBeUndefined();
    expect(resolveFieldCurrency("currency", { doc: {} })).toBeUndefined();
  });

  // 2. options = sibling fieldname on the doc.
  it("reads the currency from the named sibling field on the doc", () => {
    expect(
      resolveFieldCurrency("currency", {
        doc: { currency: "EUR" },
        defaultCurrency: "USD",
      })
    ).toBe("EUR");
  });

  it("falls back to the default when the sibling field is empty", () => {
    expect(
      resolveFieldCurrency("currency", {
        doc: { currency: "" },
        defaultCurrency: "USD",
      })
    ).toBe("USD");
  });

  // 3. Child-table cell: row wins, then doc, then default.
  it("prefers the row column over the doc for a grid cell", () => {
    expect(
      resolveFieldCurrency("currency", {
        row: { currency: "INR" },
        doc: { currency: "EUR" },
        defaultCurrency: "USD",
      })
    ).toBe("INR");
  });

  it("falls back to the doc when the row column is empty/absent", () => {
    expect(
      resolveFieldCurrency("currency", {
        row: { currency: "" },
        doc: { currency: "EUR" },
        defaultCurrency: "USD",
      })
    ).toBe("EUR");
    expect(
      resolveFieldCurrency("currency", { row: {}, doc: { currency: "EUR" } })
    ).toBe("EUR");
  });

  it("falls back to the default when neither row nor doc has the currency", () => {
    expect(
      resolveFieldCurrency("currency", {
        row: {},
        doc: {},
        defaultCurrency: "USD",
      })
    ).toBe("USD");
  });

  // 3b. Row dialog: the row's own doc has no sibling, so the parent doc supplies
  // it — keeps the dialog's currency in sync with the grid (where the parent doc
  // is the injected `doc`).
  it("falls back to the parent doc when the row/doc lack the currency", () => {
    expect(
      resolveFieldCurrency("currency", {
        doc: { currency: "" },
        parentDoc: { currency: "EUR" },
        defaultCurrency: "USD",
      })
    ).toBe("EUR");
  });

  it("prefers a child-local sibling over the parent doc", () => {
    expect(
      resolveFieldCurrency("currency", {
        doc: { currency: "INR" },
        parentDoc: { currency: "EUR" },
        defaultCurrency: "USD",
      })
    ).toBe("INR");
  });

  it("resolves the cross-record link docname from the parent doc as a last resort", () => {
    const getDocValue = (_dt: string, name: string) =>
      name === "ParentCo" ? "JPY" : "USD";
    expect(
      resolveFieldCurrency("Company:company:default_currency", {
        doc: {},
        parentDoc: { company: "ParentCo" },
        getDocValue,
      })
    ).toBe("JPY");
  });

  // 4. Cross-record "Doctype:link_field:currency_field" form.
  it("reads the currency off the linked record via an explicit getDocValue", () => {
    const getDocValue = (dt: string, name: string, field: string) =>
      dt === "Company" && name === "Acme" && field === "default_currency"
        ? "GBP"
        : null;
    expect(
      resolveFieldCurrency("Company:company:default_currency", {
        doc: { company: "Acme" },
        getDocValue,
        defaultCurrency: "USD",
      })
    ).toBe("GBP");
  });

  it("resolves the cross-record link docname from the row first", () => {
    const getDocValue = (_dt: string, name: string) =>
      name === "RowCo" ? "JPY" : "USD";
    expect(
      resolveFieldCurrency("Company:company:default_currency", {
        row: { company: "RowCo" },
        doc: { company: "DocCo" },
        getDocValue,
      })
    ).toBe("JPY");
  });

  it("uses the registered default reader when ctx omits getDocValue", () => {
    setDocValueReader((dt, name, field) =>
      dt === "Company" && name === "Acme" && field === "default_currency"
        ? "CHF"
        : null
    );
    expect(
      resolveFieldCurrency("Company:company:default_currency", {
        doc: { company: "Acme" },
        defaultCurrency: "USD",
      })
    ).toBe("CHF");
  });

  it("falls back to the default while the built-in reader has nothing yet", () => {
    // No override → built-in reader, whose read has not landed → fallback.
    expect(
      resolveFieldCurrency("Company:company:default_currency", {
        doc: { company: "Acme" },
        defaultCurrency: "USD",
      })
    ).toBe("USD");
  });

  it("falls back to the default when the cross-record link docname is missing", () => {
    setDocValueReader(() => "GBP");
    expect(
      resolveFieldCurrency("Company:company:default_currency", {
        doc: {},
        defaultCurrency: "USD",
      })
    ).toBe("USD");
  });
});

describe("doc-value reader seam", () => {
  it("returns the override when set, else a read of the cache", () => {
    const builtin = getDocValueReader();
    const stub = () => "USD";
    setDocValueReader(stub);
    expect(getDocValueReader()).toBe(stub);
    resetDocValueReader();
    expect(getDocValueReader()).toBe(builtin);
  });
});

describe("the built-in reader", () => {
  const scopes: EffectScope[] = [];

  /** A component on screen: its reader, and a currency shown the way a field shows it. */
  function visit() {
    const scope = effectScope();
    scopes.push(scope);
    return scope.run(() => {
      const read = useDocValueReader();
      const shown = computed(() =>
        resolveFieldCurrency("Company:company:default_currency", {
          doc: { company: "Acme" },
          defaultCurrency: "USD",
          getDocValue: read,
        })
      );
      return { read, shown, leave: () => scope.stop() };
    })!;
  }

  afterEach(() => scopes.splice(0).forEach((scope) => scope.stop()));

  it("reads the cache alone outside a component", () => {
    const read = useDocValueReader();
    expect(read("Company", "Acme", "default_currency")).toBeUndefined();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("lets the override answer for a component's reader", () => {
    const { read } = visit();
    setDocValueReader(() => "CHF");
    expect(read("Company", "Acme", "default_currency")).toBe("CHF");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("reads the value into the cache and makes no list entry", async () => {
    const answer = respondLater();
    const { shown } = visit();
    expect(shown.value).toBe("USD");

    const query = new URL(String(fetchMock.mock.calls[0][0]), "http://x").searchParams;
    expect(JSON.parse(query.get("fields")!)).toEqual(["default_currency", "name", "modified"]);
    expect(JSON.parse(query.get("filters")!)).toEqual({ name: "Acme" });

    answer({ data: [acme("EUR")], has_next_page: false });
    await flush();
    expect(shown.value).toBe("EUR");
    expect(readCachedDocument("Company", "Acme")!.doc.default_currency).toBe("EUR");
    const fields = ["default_currency", "name", "modified"];
    expect(readCachedList("Company", { fields, filters: { name: "Acme" }, limit: 1 })).toBe(
      undefined
    );
  });

  it("sends one read while many readers on screen use a value", async () => {
    const answer = respondLater();
    const first = visit();
    const second = visit();
    for (let run = 0; run < 5; run++) {
      first.read("Company", "Acme", "default_currency");
      second.read("Company", "Acme", "default_currency");
    }
    answer({ data: [acme("EUR")], has_next_page: false });
    await flush();
    expect(second.shown.value).toBe("EUR");
    first.leave();
    visit().read("Company", "Acme", "default_currency");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("shows a changed linked currency on the next visit, with no reload", async () => {
    respond({ data: [acme("EUR")], has_next_page: false });
    const first = visit();
    first.shown.value;
    await flush();
    expect(first.shown.value).toBe("EUR");
    first.leave();

    const answer = respondLater();
    const second = visit();
    expect(second.shown.value).toBe("EUR");
    expect(fetchMock).toHaveBeenCalledTimes(2);

    answer({ data: [acme("GBP", NEW)], has_next_page: false });
    await flush();
    expect(second.shown.value).toBe("GBP");
  });

  it("keeps a value on screen past the cache's limit of field reads", async () => {
    respond({ data: [acme("EUR")], has_next_page: false });
    const { shown } = visit();
    shown.value;
    await flush();
    for (let index = 0; index < 60; index++) {
      feedFieldRead(takeTicket(), "Company", { name: `C${index}`, modified: OLD });
    }
    expect(shown.value).toBe("EUR");
  });

  it("shows a save of the linked record with no read of its own", async () => {
    respond({ data: [acme("EUR")], has_next_page: false });
    const { shown } = visit();
    shown.value;
    await flush();

    respond({ data: acme("GBP", NEW) });
    await updateDocument("Company", "Acme", { default_currency: "GBP", modified: OLD });
    expect(shown.value).toBe("GBP");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("does not retry a failed read in the same visit, and retries on the next", async () => {
    respond({ errors: [{ message: "Forbidden" }] }, 403);
    const first = visit();
    first.shown.value;
    await flush();
    first.read("Company", "Acme", "default_currency");
    expect(first.shown.value).toBe("USD");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    first.leave();

    respond({ data: [acme("EUR")], has_next_page: false });
    const second = visit();
    second.shown.value;
    await flush();
    expect(second.shown.value).toBe("EUR");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
