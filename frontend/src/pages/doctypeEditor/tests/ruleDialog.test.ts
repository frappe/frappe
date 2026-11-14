// The rule rows as the panel draws them: open the dialog, edit or not, close it.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, type App } from "vue";

const { toast } = vi.hoisted(() => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));
vi.mock("frappe-ui", async (importOriginal) => ({
  ...(await importOriginal<typeof import("frappe-ui")>()),
  toast,
}));

import ContainerPanel from "../ContainerPanel.vue";
import FieldRules from "../FieldRules.vue";
import RuleMark from "../RuleMark.vue";
import { mountEditor, taskNote } from "./editorFixture";

let app: App | undefined;
let stop: (() => void) | undefined;
afterEach(() => {
  app?.unmount();
  stop?.();
  app = stop = undefined;
  document.body.innerHTML = "";
});

function mount(fields: Record<string, unknown> = {}) {
  const state = taskNote();
  Object.assign(state.definition.fields[0], fields);
  const editor = mountEditor(state);
  stop = editor.stop;
  const host = document.body.appendChild(document.createElement("div"));
  app = createApp({
    render: () =>
      h(FieldRules, {
        canvas: editor.canvas,
        field: editor.canvas.field("subject")!,
      }),
  });
  app.mount(host);
  return editor;
}

async function settle() {
  for (let i = 0; i < 4; i++) await nextTick();
  await new Promise((resolve) => setTimeout(resolve, 0));
}

function row(key: string) {
  return document.querySelector<HTMLButtonElement>(
    `[data-rule-row="subject.${key}"]`
  )!;
}

async function openRow(key: string) {
  return openButton(row(key));
}

/** The builder loads on demand, so the dialog is ready only when its editor has rendered. */
async function openButton(button: HTMLButtonElement) {
  button.click();
  await vi.waitFor(() =>
    expect(document.querySelector("[data-rule-editor]")).not.toBeNull()
  );
  await settle();
  return document.querySelector("[data-rule-editor]")!;
}

async function done() {
  document.querySelector<HTMLButtonElement>("[data-rule-done]")!.click();
  await settle();
}

describe("the rule dialog", () => {
  it("shows each row's words in the panel", () => {
    mount({ depends_on: "eval:doc.status=='Open'" });
    expect(row("depends_on").textContent).toContain("Status is Open");
    expect(row("mandatory_depends_on").textContent).toContain("Never");
  });

  it("opens a 2xl dialog titled with the rule and the field, with Rules | Code and Done in its footer", async () => {
    mount();
    await openRow("mandatory_depends_on");
    const dialog = document.querySelector<HTMLElement>("[role=dialog]")!;
    expect(dialog.getAttribute("aria-labelledby")).toBeTruthy();
    expect(
      document.getElementById(dialog.getAttribute("aria-labelledby")!)!
        .textContent
    ).toBe("Mandatory if · Subject");
    expect(dialog.className).toContain("max-w-2xl");
    const footer = document.querySelector("[data-rule-done]")!.parentElement!;
    expect(footer.querySelector("[data-rule-mode]")).not.toBeNull();
    expect(footer.querySelector("[data-rule-clear]")!.textContent).toBe(
      "Clear condition"
    );
    expect(document.querySelector("[data-rule-done]")!.className).toContain(
      "bg-surface-gray-9"
    );
  });

  it("keeps an unreadable rule as written: open in Code, closed with nothing staged", async () => {
    const raw = "eval:frappe.user.has_role('Accounts User')";
    const editor = mount({ read_only_depends_on: raw });
    const builder = await openRow("read_only_depends_on");
    expect(
      builder.querySelector<HTMLTextAreaElement>("[data-rule-code]")!.value
    ).toBe("frappe.user.has_role('Accounts User')");
    await done();
    expect(document.querySelector("[data-rule-editor]")).toBeNull();
    expect(editor.edits.staged.value).toEqual([]);
  });

  it("stages an edited rule once, as one undo step, when the dialog closes", async () => {
    const editor = mount({ depends_on: "eval:doc.status=='Open'" });
    const builder = await openRow("depends_on");
    builder.querySelector<HTMLButtonElement>("[data-rule-clear]")!.click();
    await settle();
    expect(editor.edits.staged.value).toEqual([]);
    await done();
    expect(editor.edits.staged.value).toEqual([
      {
        act: "fields.set_field_property",
        fieldname: "subject",
        property: "depends_on",
        value: "",
      },
    ]);
    expect(row("depends_on").textContent).toContain("Always");
  });

  it("opens only the row clicked last while the builder loads", async () => {
    mount();
    row("depends_on").click();
    await openRow("mandatory_depends_on");
    expect(document.querySelectorAll("[data-rule-editor]")).toHaveLength(1);
    expect(row("depends_on").getAttribute("aria-expanded")).toBe("false");
    expect(row("mandatory_depends_on").getAttribute("aria-expanded")).toBe(
      "true"
    );
  });

  it.each([
    [
      "a click outside",
      () =>
        document.body.dispatchEvent(
          new Event("pointerdown", { bubbles: true })
        ),
    ],
    [
      "Escape",
      () =>
        document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" })),
    ],
  ])(
    "drops the pending open on %s while the builder loads",
    async (_, dismiss) => {
      mount();
      row("depends_on").click();
      dismiss();
      await settle();
      await settle();
      expect(document.querySelector("[data-rule-editor]")).toBeNull();
      expect(row("depends_on").getAttribute("aria-expanded")).toBe("false");
    }
  );
});

describe("a container's rule rows", () => {
  it("says a section's Visible if, and stages an edit to it with the container act", async () => {
    const editor = mountEditor(taskNote());
    stop = editor.stop;
    const host = document.body.appendChild(document.createElement("div"));
    const selection = { kind: "section" as const, section: "more" };
    app = createApp({
      render: () => h(ContainerPanel, { canvas: editor.canvas, selection }),
    });
    app.mount(host);
    await settle();
    const visible = document.querySelector<HTMLButtonElement>(
      '[data-rule-row="more.dependsOn"]'
    )!;
    expect(visible.textContent).toContain("Status is set");
    expect(
      document.querySelector('[data-rule-row="more.collapsibleDependsOn"]')
    ).toBeNull();

    await openButton(visible);
    expect(document.querySelector("[role=dialog]")!.textContent).toContain(
      "Visible if · Untitled section"
    );
    document.querySelector<HTMLButtonElement>("[data-rule-clear]")!.click();
    await settle();
    await done();
    expect(editor.edits.staged.value).toHaveLength(1);
    expect(editor.edits.staged.value[0]).toMatchObject({
      act: "canvas.set_container_property",
      container: "more",
      property: "dependsOn",
      value: "",
    });
  });
});

describe("the canvas mark", () => {
  it("marks a field or container that has a rule, and nothing else", async () => {
    const editor = mountEditor(taskNote());
    stop = editor.stop;
    const { canvas } = editor;
    const [main, more] = canvas.tabs.value[0].sections;
    const host = document.body.appendChild(document.createElement("div"));
    app = createApp({
      render: () => [
        h(RuleMark, {
          canvas,
          kind: "section",
          node: more,
          "data-host": "more",
        }),
        h(RuleMark, {
          canvas,
          kind: "section",
          node: main,
          "data-host": "main",
        }),
        h(RuleMark, {
          canvas,
          kind: "field",
          node: canvas.field("subject"),
          "data-host": "subject",
        }),
      ],
    });
    app.mount(host);
    await settle();
    const marks = [...document.querySelectorAll("[data-rule-mark]")];
    expect(marks.map((one) => one.getAttribute("data-host"))).toEqual(["more"]);
    expect(
      marks[0].querySelector("[aria-label]")!.getAttribute("aria-label")
    ).toBe("Visible if Status is set");
  });
});
