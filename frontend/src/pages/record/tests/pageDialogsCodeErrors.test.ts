// A page dialog draws its own form, so the record's compile errors do not reach it.
import { describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, inject, nextTick, ref } from "vue";
import { CodeErrorsKey } from "@framework/ui/components/Fields/types";

// The chrome is frappe-ui's; a passthrough here reads what the host provides, not reka-ui's transitions.
vi.mock("frappe-ui", () => ({
  Dialog: defineComponent({
    setup: (_, { slots }) => () => h("div", slots.default?.()),
  }),
  Button: defineComponent({ setup: () => () => h("button") }),
  ErrorMessage: defineComponent({ setup: () => () => h("p") }),
  Skeleton: defineComponent({ setup: () => () => h("div") }),
  toast: { success: vi.fn(), error: vi.fn() },
}));

import PageDialogs from "../dialogs/PageDialogs.vue";

describe("PageDialogs", () => {
  it("cuts the record's compile errors off from a dialog's body", async () => {
    const seen: unknown[] = [];
    const Body = defineComponent({
      setup() {
        seen.push(inject(CodeErrorsKey, undefined));
        return () => h("div");
      },
    });
    const entry = {
      id: 1,
      kind: "open",
      component: Body,
      props: {},
      options: { title: "A form" },
      settle: vi.fn(),
      dismiss: vi.fn(),
    };
    const controller = { dialogs: ref([entry]) };
    const errors = ref([{ field: "script", line: 1, column: 1, message: "Bad" }]);

    const app = createApp({ render: () => h(PageDialogs, { controller: controller as any }) });
    app.provide(CodeErrorsKey, errors);
    app.mount(document.createElement("div"));
    await nextTick();

    expect(seen).toEqual([null]);
    app.unmount();
  });
});
