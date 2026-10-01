// Vue colors and completion inside a script's `template:` strings.
import { completionStatus, currentCompletions, startCompletion } from "@codemirror/autocomplete";
import { ensureSyntaxTree } from "@codemirror/language";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick } from "vue";
import CodeEditorField from "../CodeEditorField.vue";
import { templateLanguage } from "../templateLanguage";
import { TemplateNamesKey } from "../types";

function stateOf(doc: string, names: readonly string[] | null = null) {
  return EditorState.create({ doc, extensions: templateLanguage(names) });
}

function nodeAt(doc: string, marker: string) {
  const state = stateOf(doc);
  const tree = ensureSyntaxTree(state, state.doc.length, 5000)!;
  return tree.resolveInner(doc.indexOf(marker) + 1, 1).name;
}

describe("template language", () => {
  it("parses a template: string as Vue", () => {
    expect(nodeAt('export default { template: "<div/>" };', "div")).toBe("TagName");
    expect(nodeAt("export default { template: `<div/>` };", "div")).toBe("TagName");
  });

  it("leaves every other string as JavaScript", () => {
    expect(nodeAt('x = { "template": "<div/>" };', "div")).toBe("String");
    expect(nodeAt('x = { other: "<div/>" };', "div")).toBe("String");
    expect(nodeAt('x = { ["template"]: "<div/>" };', "div")).toBe("String");
    expect(nodeAt("x = { template: `<div>${a}</div>` };", "div")).toBe("TemplateString");
    expect(nodeAt('const { template = "<div/>" } = x;', "div")).toBe("String");
  });

  it("parses a quoted template as the compiler decodes its escapes", () => {
    const double = 'x = { template: "<div v-if=\\"ready\\">x</div>" };';
    expect(nodeAt(double, "v-if")).toBe("VueAttributeName");
    expect(nodeAt(double, "ready")).toBe("VariableName");
    const single = "x = { template: '<div v-if=\\'ready\\'>x</div>' };";
    expect(nodeAt(single, "v-if")).toBe("VueAttributeName");
    expect(nodeAt(single, "ready")).toBe("VariableName");
  });
});

const BUILT_INS = ["KeepAlive", "Suspense", "Teleport", "Transition", "TransitionGroup"];
const DIRECTIVES = [
  "v-bind",
  "v-cloak",
  "v-else",
  "v-else-if",
  "v-for",
  "v-html",
  "v-if",
  "v-memo",
  "v-model",
  "v-on",
  "v-once",
  "v-pre",
  "v-show",
  "v-slot",
  "v-text",
];

// The document's `|` marks the cursor; the result is every label the editor offers there.
async function complete(marked: string, names: readonly string[] | null = null) {
  const view = new EditorView({
    state: stateOf(marked.replace("|", ""), names),
    parent: document.body,
  });
  const labels = await completionsAt(view, marked.indexOf("|"));
  view.destroy();
  return labels;
}

async function completionsAt(view: EditorView, pos: number) {
  view.dispatch({ selection: { anchor: pos } });
  ensureSyntaxTree(view.state, view.state.doc.length, 5000);
  startCompletion(view);
  await vi.waitFor(() => expect(completionStatus(view.state)).not.toBe("pending"));
  return currentCompletions(view.state).map((option) => option.label);
}

describe("template completion", () => {
  const SCRIPT = (template: string) =>
    "export default {\n" +
    '  components: { RowCard, "status-pill": Pill },\n' +
    `  template: \`${template}\`,\n};`;

  it("offers the script's components and the host's names at a tag", async () => {
    const labels = await complete(SCRIPT("<div><|</div>"), ["FeatherIcon"]);
    expect(labels.sort()).toEqual(["FeatherIcon", "RowCard", "status-pill"]);
  });

  it("offers only the built-ins with no host names", async () => {
    const labels = await complete('export default { template: "<|" };');
    expect(labels.sort()).toEqual(BUILT_INS);
  });

  it("offers names at a tag after an escape", async () => {
    const labels = await complete('x = { template: "<div class=\\"a\\"><Fe|" };', ["FeatherIcon"]);
    expect(labels).toEqual(["FeatherIcon"]);
  });

  it("offers v- words at an attribute", async () => {
    expect((await complete(SCRIPT("<div |></div>"))).sort()).toEqual(DIRECTIVES);
    expect(await complete(SCRIPT("<div v-sh|></div>"))).toEqual(["v-show"]);
  });

  it("offers nothing outside a template", async () => {
    expect(await complete("const value = cons|", ["FeatherIcon"])).toEqual([]);
    expect(await complete('x = { other: "<Ro|" };', ["FeatherIcon"])).toEqual([]);
  });
});

describe("Code field", () => {
  it("completes the host's template names in a JavaScript field", async () => {
    const script = 'export default { template: "<" };';
    const field = { fieldname: "script", fieldtype: "Code", options: "JavaScript" };
    const host = document.body.appendChild(document.createElement("div"));
    const app = createApp({ render: () => h(CodeEditorField, { field, modelValue: script }) });
    app.provide(TemplateNamesKey, ["FeatherIcon"]);
    app.mount(host);
    await nextTick();
    const view = EditorView.findFromDOM(host.querySelector(".cm-editor") as HTMLElement)!;

    await vi.waitFor(async () =>
      expect(await completionsAt(view, script.indexOf("<") + 1)).toEqual(["FeatherIcon"])
    );
    app.unmount();
    host.remove();
  });
});
