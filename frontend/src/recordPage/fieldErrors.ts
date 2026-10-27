// The errors a form marks on its fields, keyed by `fieldErrorKey`. A mark made during a
// replay or a hold lands when it commits, as the overlays' ops do.
import { shallowRef } from "vue";
import type { FieldError as RefusedField } from "@framework/ui/api";
import { identify, rowKey } from "@framework/ui/fields";
import {
  fieldErrorKey,
  markedFieldnames,
  type CommitChannel,
  type FieldAddress,
  type FieldError,
  type RowAddress,
} from "@framework/ui/fields/types";
import type { FormLayoutSchema } from "@framework/ui/FormLayout/types";
import { shownFields } from "./requiredFields";
import type { Staging } from "@/pageEngine/staging";

interface Mark {
  message: FieldError;
  /** The source that set it, or `""` for the host's own marks. */
  source: string;
}

type Marks = Map<string, Mark>;

export class FieldErrors implements Staging {
  /** What a host provides as `FieldErrorsKey`. */
  readonly drawn = shallowRef<Readonly<Record<string, FieldError>>>({});
  private shown: Marks = new Map();
  private staged: Marks | null = null;
  private depth = 0;

  mark(address: FieldAddress, message: FieldError, source = "") {
    const marks = this.staged ?? new Map(this.shown);
    marks.set(fieldErrorKey(address), { message, source });
    if (!this.staged) this.draw(marks);
  }

  unmark(address: FieldAddress) {
    const marks = this.staged ?? new Map(this.shown);
    marks.delete(fieldErrorKey(address));
    if (!this.staged) this.draw(marks);
  }

  /** An edit's clear: off the screen now, and out of any replay or hold in flight. */
  clear(address: FieldAddress) {
    const key = fieldErrorKey(address);
    this.staged?.delete(key);
    if (!this.shown.has(key)) return;
    const marks = new Map(this.shown);
    marks.delete(key);
    this.draw(marks);
  }

  /** A save's start: every mark goes, drawn or staged. */
  clearAll() {
    this.staged?.clear();
    if (this.shown.size) this.draw(new Map());
  }

  /** Marks each field a refused save names; a row is found by its name, then by its position. */
  markRefused(refused: RefusedField[] | undefined, doc: Record<string, any>) {
    for (const { fieldname, parentfield, row, idx, message } of refused ?? []) {
      if (!parentfield) {
        this.mark(fieldname, message);
        continue;
      }
      const table: Record<string, any>[] = Array.isArray(doc[parentfield]) ? doc[parentfield] : [];
      const atIdx = idx ? table[idx - 1] : undefined;
      // A row named by the server's own insert is still unnamed in the draft.
      const found = row ? (table.find((one) => one.name === row) ?? (atIdx?.name ? undefined : atIdx)) : atIdx;
      if (found) this.mark({ parentfield, key: rowKey(identify(found))!, fieldname }, message);
    }
  }

  /** The first shown field, in form order, that holds a mark or a marked row cell. */
  firstMarked(layout: FormLayoutSchema, doc: Record<string, any>): string | undefined {
    const marked = markedFieldnames(Object.fromEntries(this.staged ?? this.shown));
    if (!marked.size) return undefined;
    return shownFields(layout, doc).find((field) => marked.has(field.fieldname))?.fieldname;
  }

  /** `channel`, clearing a field's mark on its live edit, a table's when a row comes or goes, and a removed row's. */
  clearingOnEdit<Channel extends CommitChannel>(channel: Channel): Channel {
    return {
      ...channel,
      pending: (fieldname, value, row) => {
        this.clear(row ? { ...row, fieldname } : fieldname);
        channel.pending(fieldname, value, row);
      },
      rowChanged: (row, change) => {
        this.clear(row.parentfield);
        if (change === "remove") this.clearRow(row);
        channel.rowChanged(row, change);
      },
    };
  }

  /** A replay rebuilds every mark, so it starts empty. */
  beginReplay() {
    this.staged = new Map();
    this.depth += 1;
  }

  beginHold() {
    if (!this.depth) this.staged = new Map(this.shown);
    this.depth += 1;
  }

  commit() {
    if (!this.depth) return;
    this.depth -= 1;
    if (this.depth) return;
    const staged = this.staged!;
    this.staged = null;
    this.draw(staged);
  }

  publishStaged(except: ReadonlySet<string>) {
    if (!this.staged) return;
    this.draw(new Map([...this.staged].filter(([, mark]) => !except.has(mark.source))));
  }

  /** A removed row's cells: their marks have nowhere left to draw. */
  private clearRow({ parentfield, key }: RowAddress) {
    const cells = [...new Set([...(this.staged?.keys() ?? []), ...this.shown.keys()])]
      .filter((one) => one.startsWith("["))
      .map((one) => JSON.parse(one) as [string, string, string])
      .filter(([table, row]) => table === parentfield && row === key);
    for (const [, , fieldname] of cells) this.clear({ parentfield, key, fieldname });
  }

  private draw(marks: Marks) {
    this.shown = marks;
    this.drawn.value = Object.fromEntries([...marks].map(([key, mark]) => [key, mark.message]));
  }
}
