// The search filters a Table MultiSelect's picker sends: its Link column's, under the field's own.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h } from "vue";
import type { App } from "vue";
import type { FieldMeta } from "../types";

const sent = vi.hoisted(() => ({ filters: undefined as unknown }));

vi.mock("../../TableMultiSelect", () => ({
  TableMultiSelect: defineComponent({
    props: ["filters"],
    setup(props) {
      return () => {
        sent.filters = props.filters;
        return h("div");
      };
    },
  }),
}));

const { default: TableMultiSelectField } = await import("../TableMultiSelectField.vue");

let app: App | undefined;

afterEach(() => {
  app?.unmount();
  app = undefined;
  sent.filters = undefined;
});

function render(field: Partial<FieldMeta>, column: Partial<FieldMeta> = {}) {
  app = createApp({
    render: () =>
      h(TableMultiSelectField, {
        field: {
          fieldname: "users",
          fieldtype: "Table MultiSelect",
          options: "Rule User",
          childFields: [{ fieldname: "user", fieldtype: "Link", options: "User", ...column }],
          ...field,
        },
        modelValue: [],
      }),
  });
  app.mount(document.createElement("div"));
}

describe("a Table MultiSelect's search filters", () => {
  it("are the field's own when its Link column has none", () => {
    render({ filters: { enabled: 1 } });
    expect(sent.filters).toEqual({ enabled: 1 });
  });

  it("take the Link column's, the field's own winning on a shared key", () => {
    render({ filters: { user_type: "System User" } }, { filters: { enabled: 1, user_type: "Website User" } });
    expect(sent.filters).toEqual({ enabled: 1, user_type: "System User" });
  });
});
