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

function marked(props: Record<string, unknown>) {
  host = document.createElement("div");
  document.body.appendChild(host);
  const doc = ref<Record<string, any>>({});
  app = createApp({
    render: () =>
      h(FormLayout, { layout: LAYOUT, doc: doc.value, "onUpdate:doc": () => {}, ...props }),
  });
  app.provide(CommitKey, NO_COMMIT);
  app.mount(host);
  return [...host.querySelectorAll("[autofocus]")].map((el) => el.getAttribute("data-fieldname"));
}

describe("autofocus", () => {
  it("marks only the first visible, writable field that holds a value", () => {
    expect(marked({ autofocus: true })).toEqual(["title"]);
  });

  it("marks nothing without the prop", () => {
    expect(marked({})).toEqual([]);
  });
});
