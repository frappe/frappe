# List

The table a doctype list page renders, with the footer and the selection bar beside it.
`List` draws frappe-ui's list molecule: a sticky header with sort and drag-resize, a
checkbox column with select-all, and rows that are links. It fetches and stores nothing.
The host owns the rows, the paging, the columns it binds, and what a bulk action does.

<ComponentPreview name="List-Default" />

`columns` is the `Column[]` Column Settings emits, plus an optional `align`. `rows` is
plain objects; `rowKey` names the property that identifies a row and defaults to `name`.
`rowLink(row)` returns the route a row opens, so every row renders as a `RouterLink`.
Selection is by `String(row[rowKey])`, so `selection` holds names as strings.

## Header sort

Binding `v-model:sort` is what makes the headers sortable. The model is the same `Sort[]`
the Sort By control edits. A header click sets that column as the whole sort, and a
second click flips its direction.

## Cells

The `cell` slot replaces the text for a column and keeps the row a link. It receives the
`row`, the `column` and the default `value` text. Columns the slot does not handle keep
the default.

<ComponentPreview name="List-Cells" />

## Loading and empty

`loading` with no rows draws skeleton rows in the column tracks. No rows and not loading
draws the `empty` slot.

<ComponentPreview name="List-States" />

## Column widths

Drag the handle at a header's right edge to resize; double-click it to reset. `List` emits
`column-resize` with `{ fieldname, width }` and `column-reset` with `{ fieldname }`, and
the host writes the width into its columns with the same helpers Column Settings uses.

<ComponentPreview name="List-Resize" />

## Virtual rows

Rows are windowed against the list's own scroll viewport. `rowHeight` fixes the height the
window needs; the default is 40px.

<ComponentPreview name="List-Virtual" />

## ListFooter

The page-size tabs bind `pageSize`; `page-size` fires only for a click. Load More emits
`load-more` while `rowCount` is below `totalCount`. With `hasCounts` off the count is a
skeleton.

<ComponentPreview name="List-Footer" />

## ListBulkBar

Shows while `selection` has rows and floats over a `relative` host. Each action gets the
selection; the clear button empties it.

<ComponentPreview name="List-BulkBar" />

## Composed

The three together, as a list page lays them out.

<ComponentPreview name="List-Composed" />
