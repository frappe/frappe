// The runs of `list.set_columns`, `list.set_page_size` and `list.load_more`, which the List renderer owns; loaded on first use.
import { nextTick } from "vue";
import { ActInvalid } from "@/acts/dispatcher";
import type { ListView } from "@/list/useListView";
import { columnsFrom } from "@/list/storedSettings";
import { getColumnOptions } from "@framework/ui/ColumnSettings";
import { loadedRows, oneOf } from "./listStateRuns";

export async function setColumns(view: ListView, { columns }: { columns: { fieldname: string }[] }) {
  const meta = view.meta.value;
  if (!meta) throw new Error("the list has not loaded its fields yet");
  // As the Columns dialog's reset: no columns of the person's own, so the site's or the app's show.
  if (!columns.length) await view.resetColumns();
  else view.columns.value = parseColumns(columns, view);
  await nextTick(); // the new fields reload the rows
  await view.settled();
  return { columns: view.columns.value.map(({ fieldname, label }) => ({ fieldname, label })) };
}

export async function setPageSize(view: ListView, { size }: { size: number }) {
  view.pageSize.value = size;
  view.show(size);
  await view.settled();
  return rowsRead(view);
}

export async function loadMore(view: ListView) {
  await view.settled(); // next() does nothing while a page is on its way
  if (!view.hasNextPage.value) throw new ActInvalid("list.load_more", "every matching row is loaded already");
  view.next();
  await view.settled();
  return rowsRead(view);
}

function rowsRead(view: ListView) {
  return loadedRows(view.rows.value, view.totalCount.value, view.meta.value?.title_field);
}

/** The columns as the dialog's v-model holds them: kept widths, the field's own label. */
function parseColumns(entries: { fieldname: string }[], view: ListView) {
  const fields = view.meta.value!.fields ?? [];
  const choices = getColumnOptions(fields, [], view.meta.value!).filter(({ fieldname }) => view.readable(fieldname));
  const allowed = new Set(choices.map(({ fieldname }) => fieldname));
  const seen = new Set<string>();
  entries.forEach(({ fieldname }, index) => {
    const at = `columns[${index}]`;
    if (!allowed.has(fieldname))
      throw new ActInvalid("list.set_columns", `${at}: ${fieldname} is not a field this list can show; use one of ${oneOf([...allowed])}`);
    if (seen.has(fieldname)) throw new ActInvalid("list.set_columns", `${at}: ${fieldname} is listed twice`);
    seen.add(fieldname);
  });
  const widths = new Map(view.columns.value.map(({ fieldname, width }) => [fieldname, width]));
  const kept = entries.map(({ fieldname }) => ({ fieldname, width: widths.get(fieldname) }));
  return columnsFrom(kept, fields, view.readable, view.meta.value!);
}

/** The run of each act, by act name. */
export const RUNS: Record<string, (view: ListView, value: any) => Promise<unknown>> = {
  set_columns: setColumns,
  set_page_size: setPageSize,
  load_more: loadMore,
};
