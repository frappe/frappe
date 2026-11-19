// Lint marks for the compile errors a host sends to a Code field.
import type { Diagnostic } from "@codemirror/lint";
import type { Text } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import type { CodeError } from "../../api/envelope";

type Lint = typeof import("@codemirror/lint");

/** Marks `errors` in `view` and puts the cursor on the first; an empty list clears the marks. */
export function markCodeErrors(view: EditorView, errors: readonly CodeError[], lint: Lint) {
  const diagnostics = diagnosticsFor(view.state.doc, errors);
  view.dispatch(lint.setDiagnostics(view.state, diagnostics));
  const first = diagnostics[0];
  if (!first) return;
  view.dispatch({
    selection: { anchor: first.from },
    effects: EditorView.scrollIntoView(first.from, { y: "center" }),
  });
}

/** The marks for `errors` in `doc`. A line or column past the text lands at its end. */
export function diagnosticsFor(doc: Text, errors: readonly CodeError[]): Diagnostic[] {
  return errors.map((error) => {
    const line = doc.line(clamp(error.line, 1, doc.lines));
    const from = line.from + clamp(error.column - 1, 0, line.length);
    return { from, to: Math.min(from + 1, line.to), severity: "error", message: error.message };
  });
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}
