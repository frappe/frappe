import { afterEach, describe, expect, it } from "vitest";
import { createApp, defineComponent, h } from "vue";
import type { App } from "vue";
import FormLayoutColumn from "../FormLayoutColumn.vue";
import { CommitKey, DocKey, ResolveFieldKey, UpdateKey } from "../types";
import type { CommitChannel, FieldNode } from "../types";

/**
 * The commit channel, meta → DOM: a widget's live `update:modelValue` marks the
 * field pending and its `change` commits it, with no diffing anywhere between.
 */

// Emits the two events every real field component emits, on demand.
const StubField = defineComponent({
  props: { field: { type: Object, required: true }, modelValue: null },
  emits: ["update:modelValue", "change"],
  setup(props, { emit }) {
    return () =>
      h("input", {
        "data-fieldname": props.field.fieldname,
        onInput: (event: any) => emit("update:modelValue", event.target.value),
        onChange: (event: any) => emit("change", event.target.value),
      });
  },
});

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = undefined;
  host = undefined;
});

interface Recorded {
  channel: CommitChannel;
  pending: [string, any][];
  committed: [string, any][];
}

function recorder(): Recorded {
  const pending: [string, any][] = [];
  const committed: [string, any][] = [];
  return {
    pending,
    committed,
    channel: {
      pending: (fieldname, value) => pending.push([fieldname, value]),
      commit: (fieldname, value) => committed.push([fieldname, value]),
      rowChanged: () => {},
    },
  };
}

function render(fields: FieldNode[], channel?: CommitChannel) {
  const doc: Record<string, any> = {};
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () => h(FormLayoutColumn, { column: { name: "c", fields } }),
  });
  app.provide(DocKey, { value: doc } as any);
  app.provide(UpdateKey, (name: string, value: any) => (doc[name] = value));
  app.provide(ResolveFieldKey, () => StubField);
  if (channel) app.provide(CommitKey, channel);
  app.mount(host);
  return { host, doc };
}

const qty: FieldNode = { fieldname: "qty", fieldtype: "Float" };

function type(host: HTMLElement, value: string) {
  const input = host.querySelector("input")! as HTMLInputElement;
  input.value = value;
  input.dispatchEvent(new Event("input"));
}

function blur(host: HTMLElement) {
  host.querySelector("input")!.dispatchEvent(new Event("change"));
}

describe("commit wiring", () => {
  it("marks the field pending as it is typed, and commits on change", () => {
    const recorded = recorder();
    const { host, doc } = render([qty], recorded.channel);

    type(host, "10");
    expect(doc.qty).toBe("10");
    expect(recorded.pending).toEqual([["qty", "10"]]);
    expect(recorded.committed).toEqual([]);

    blur(host);
    expect(recorded.committed).toEqual([["qty", "10"]]);
  });

  it("commits once per commit, however many keystrokes preceded it", () => {
    const recorded = recorder();
    const { host } = render([qty], recorded.channel);
    type(host, "1");
    type(host, "10");
    blur(host);
    expect(recorded.committed).toEqual([["qty", "10"]]);
  });

  it("a child table commits through its rows, not under its own fieldname", () => {
    const recorded = recorder();
    const { host } = render(
      [{ fieldname: "products", fieldtype: "Table" }],
      recorded.channel
    );
    type(host, "anything");
    blur(host);
    expect(recorded.pending).toEqual([]);
    expect(recorded.committed).toEqual([]);
  });

  it("still syncs the doc when no channel is provided", () => {
    const { host, doc } = render([qty]);
    type(host, "7");
    blur(host);
    expect(doc.qty).toBe("7");
  });
});
