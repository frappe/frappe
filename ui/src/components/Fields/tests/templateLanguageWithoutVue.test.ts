// An app built on develop never installed `@codemirror/lang-vue`; its build stands in
// `vueLanguage` with undefined (ui/vite), and a `template:` string stays plain JavaScript.
import { ensureSyntaxTree } from "@codemirror/language";
import { EditorState } from "@codemirror/state";
import { describe, expect, it, vi } from "vitest";

vi.mock("@codemirror/lang-vue", () => ({ vueLanguage: undefined }));

import { templateLanguage } from "../templateLanguage";

describe("template language without lang-vue", () => {
  it("leaves a template: string as a JavaScript string", () => {
    const doc = 'export default { template: "<div/>" };';
    const state = EditorState.create({ doc, extensions: templateLanguage(null) });
    const tree = ensureSyntaxTree(state, state.doc.length, 5000)!;
    expect(tree.resolveInner(doc.indexOf("div") + 1, 1).name).toBe("String");
  });
});
