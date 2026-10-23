// `autofocus` marks the first field a person can type into, for a frappe-ui Dialog to focus.
import { afterEach, describe, expect, it } from "vitest";
import { createApp, h, ref } from "vue";
import type { App } from "vue";
import FormLayout from "../FormLayout.vue";
import { CommitKey, NO_COMMIT } from "../types";
import type { FormLayoutSchema } from "../types";

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
});

const LAYOUT: FormLayoutSchema = [
  {
    sections: [
      {
        columns: [
          {
            fields: [
              { fieldname: "intro", fieldtype: "Heading", label: "Intro" },
              { fieldname: "owner", fieldtype: "Data", label: "Owner", readOnly: true },
              { fieldname: "secret", fieldtype: "Data", label: "Secret", hidden: true },
              { fieldname: "notes", fieldtype: "Data", label: "Notes", dependsOn: "eval:doc.extra" },
              { fieldname: "title", fieldtype: "Data", label: "Title" },
              { fieldname: "source", fieldtype: "Data", label: "Source" },
            ],
          },
        ],
      },
    ],
  },
] as FormLayoutSchema;

/** A closed section first, then an open one. */
const CLOSED_FIRST: FormLayoutSchema = [
  {
    name: "details",
    sections: [
      {
        name: "more",
        label: "More",
        opened: false,
        columns: [{ fields: [{ fieldname: "notes", fieldtype: "Data", label: "Notes" }] }],
      },
      { columns: [{ fields: [{ fieldname: "title", fieldtype: "Data", label: "Title" }] }] },
    ],
  },
] as FormLayoutSchema;

function marked(props: Record<string, unknown>, layout = LAYOUT) {
  host = document.createElement("div");
  document.body.appendChild(host);
  const doc = ref<Record<string, any>>({});
  app = createApp({
    render: () =>
      h(FormLayout, { layout, doc: doc.value, "onUpdate:doc": () => {}, ...props }),
  });
  app.provide(CommitKey, NO_COMMIT);
  app.mount(host);
  return [...host.querySelectorAll("[autofocus]")].map((el) => el.getAttribute("data-fieldname"));
}

describe("autofocus", () => {
  it("marks only the first visible, writable field that holds a value", () => {
    expect(marked({ autofocus: true })).toEqual(["title"]);
  });

  it("skips a closed section, unless the reader opened it", () => {
    expect(marked({ autofocus: true }, CLOSED_FIRST)).toEqual(["title"]);
    app?.unmount();
    host?.remove();
    const opened = { [JSON.stringify(["details", "more"])]: true };
    expect(marked({ autofocus: true, sections: opened }, CLOSED_FIRST)).toEqual(["notes"]);
  });

  it("marks nothing without the prop", () => {
    expect(marked({})).toEqual([]);
  });
});
