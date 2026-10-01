// What the save dialog shows for each compile error: where it is and the lines around it.
import type { CodeError } from "@framework/ui/api";
import type { RawMetaField } from "@framework/ui/components/FormLayout/types";

export interface CodeLine {
  number: number;
  text: string;
}

export interface CodeErrorFrame {
  label: string;
  line: number;
  column: number;
  message: string;
  /** The line before, the error's line and the line after, as far as the text has them. */
  lines: CodeLine[];
  /** Blanks that put a caret under the column; a tab stays a tab so the two lines align. */
  indent: string;
}

/** One frame per error, read from the draft the save sent. */
export function codeErrorFrames(
  errors: readonly CodeError[],
  doc: Record<string, any>,
  fields: RawMetaField[] | undefined,
): CodeErrorFrame[] {
  return errors.map((error) => {
    const text = String(doc[error.field] ?? "").split("\n");
    const first = Math.max(error.line - 2, 0);
    const errorLine = text[error.line - 1] ?? "";
    return {
      label: fields?.find((field) => field.fieldname === error.field)?.label || error.field,
      line: error.line,
      column: error.column,
      message: error.message,
      lines: text
        .slice(first, error.line + 1)
        .map((line, i) => ({ number: first + i + 1, text: line })),
      indent: errorLine.slice(0, Math.max(error.column - 1, 0)).replace(/[^\t]/g, " "),
    };
  });
}
