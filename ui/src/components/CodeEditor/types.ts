// Props/emits for the CodeEditor writer primitive. Kept here so the field
// wrapper and stories can share the same contract without importing the .vue.

/** A language key understood by `loadLanguage` (and `fieldtypeToLanguage`). */
export type CodeLanguage =
  | "json"
  | "html"
  | "javascript"
  | "python"
  | "sql"
  | "markdown"
  | "css"
  | "scss"
  | "yaml"
  | "xml"
  | "plain";

/**
 * Visual style variant, mirroring frappe-ui's input convention
 * (`InputVariant`): `subtle` is the filled default that sits flush with the
 * TextInput/Textarea fields around it, `outline` is a bordered-on-white box,
 * `ghost` is borderless.
 */
export type CodeEditorVariant = "subtle" | "outline" | "ghost";

export interface CodeEditorProps {
  modelValue: string;
  /** CodeMirror language key; falls through to plain text when unset/unknown. */
  language?: string;
  readonly?: boolean;
  placeholder?: string;
  /** Surface style; mirrors frappe-ui inputs. Defaults to `subtle`. */
  variant?: CodeEditorVariant;
  /**
   * CSS length capping the editor's scroll height (e.g. `"13.5rem"`). When the
   * content exceeds it the editor scrolls internally; unset means it grows to
   * fit. Pairs with the `overflow` emit so a wrapper can offer expand/collapse.
   */
  maxHeight?: string;
}

export type CodeEditorEmits = {
  /** Live document text on every change — mirrors the textarea field contract. */
  "update:modelValue": [value: string];
  /** Commit (blur). The field wrapper normalizes (e.g. JSON pretty-print) here. */
  change: [value: string];
  /** Whether the content currently exceeds `maxHeight` (only changes are emitted). */
  overflow: [overflowing: boolean];
};

export interface CodePreviewProps {
  modelValue: string;
  /** Only `markdown` / `html` render a preview; anything else renders nothing. */
  language?: string;
}
