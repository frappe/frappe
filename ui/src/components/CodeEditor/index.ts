// Code-editor primitives: a CodeMirror 6 writer (`CodeEditor`) and a sanitized
// read-only `CodePreview`, kept as two independent pieces. The code-family
// FormLayout fields (`JSON` / `Markdown Editor` / `HTML Editor` / `Code`) compose
// them through `CodeEditorField`, but both are exported so apps can build their
// own code surfaces. CodeMirror is lazy-loaded inside `CodeEditor`, so importing
// this barrel pulls in no editor code until a field actually mounts.
export { default as CodeEditor } from "./CodeEditor.vue";
export { default as CodePreview } from "./CodePreview.vue";
export { loadLanguage, fieldtypeToLanguage } from "./languages";
export type {
  CodeLanguage,
  CodeEditorVariant,
  CodeEditorProps,
  CodeEditorEmits,
  CodePreviewProps,
} from "./types";
