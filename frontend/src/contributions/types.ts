import type { Component } from "vue"
import type { ItemRenderer } from "@/navigation/types"

// The complete list of what an app may contribute; if it is not here, an app cannot do it.

type RecordHandler = (page: object, row?: object) => unknown

export type RecordHandlers = Record<string, RecordHandler | Record<string, RecordHandler>>

/** An app's item that runs the act `act` with `value(context)`; drawn while `when(context)` holds. */
export type ActionItem<Context = unknown> = {
  act: string
  label?: string
  icon?: string
  value?: (context: Context) => unknown
  when?: (context: Context) => boolean
}

/** What a list act's `run` gets, and a row action's `value` and `when` after the row. `View` is the page's view object. */
export type ListContext<View = unknown> = {
  doctype: string
  view: View
  /** The selected rows' names now; a copy, so a later selection does not change it. */
  selection: string[]
  /** The row a row action was taken on; absent for a bulk or page act. */
  row?: Record<string, unknown>
  /** Loads the rows again, as the list does after its own change. */
  reload: () => void
}

/** A list row's action; `fields` are read into the list query so `value` finds them on the row. `value` and `when` get the list's context after the row. */
export type RowAction = Omit<ActionItem, "value" | "when"> & {
  value?: (row: Record<string, unknown>, list: ListContext) => unknown
  when?: (row: Record<string, unknown>, list: ListContext) => boolean
  fields: string[]
}

export type ListHandlers = {
  columns?: { fieldname: string; width?: number }[]
  rowActions?: RowAction[]
  [key: string]: unknown
}

export type PageContribution = {
  app: string
  slug: string
  title?: string
  component: () => Promise<unknown>
}

// Fetched when the doctype's record or new-record page first opens, never with the shell.
export type LoadRecordScript = () => Promise<{ default?: RecordHandlers }>

export type DoctypeContribution =
  // Your own doctype's record page: <module>/doctype/<scrubbed>/frontend/record.js
  | { kind: 'record'; app: string; doctype: string; load: LoadRecordScript }
  // Your own doctype's list: <module>/doctype/<scrubbed>/frontend/list.js
  | { kind: 'list'; app: string; doctype: string; handlers: ListHandlers }
  // A foreign doctype: <module>/custom/<scrubbed>/record.js. Applies globally; it does not
  // move the doctype into your prefix.
  | { kind: 'custom'; app: string; doctype: string; load: LoadRecordScript }

// A page in place of a doctype's record or list page: <module>/doctype/<scrubbed>/frontend/
// pages/<name>.js, named in pages.json beside it; the same under <module>/custom/<scrubbed>/.
export type ReplacementContribution = {
  app: string
  doctype: string
  /** `record`, or a view type's name in lower case. */
  key: string
  /** The apps whose shell it applies in; absent means every app. */
  apps?: string[]
  foreign: boolean
  title?: string
  component: () => Promise<unknown>
}

// A replacement page's handler file: <name>.js beside its pages/<name>.js. It runs only on
// that page of its own app.
export type PageScriptContribution = {
  app: string
  doctype: string
  page: string
  handlers: Record<string, unknown>
}

export type StandardPages = {
  /** The page at a main list or record address: the declared page, else the standard one. */
  main: Component
  list: () => Promise<unknown>
  record: () => Promise<unknown>
  newRecord: () => Promise<unknown>
  /** The index at `/apps`, drawn with its own loading state. */
  index: Component
}

// Not contributable: a route table, a doctype opt-out, shell chrome (every error state
// included), a vite plugin or config, and a boot key from JS.

// An item kind: <module>/navigation_item_type/<scrubbed>/frontend/item.js, beside the type
// record. The framework's own kinds go through this and nothing else.
export type ItemTypeContribution = {
  app: string
  /** The type record's own `name`, read from the JSON beside the file, never guessed. */
  type: string
  renderer: ItemRenderer
}

// A view type's renderer: <module>/view_type/<scrubbed>/frontend/view.js, beside the `View Type`
// record, exporting `{ renderer: () => import(...) }`. List goes through this too.
export type ViewTypeContribution = {
  app: string
  /** The type record's own `name`, read from the JSON beside the file. */
  type: string
  renderer: () => Promise<unknown>
}

// A settings block's component: <module>/frontend/settings/<name>.vue, loaded when its pane
// opens. The app's `Settings Dialog` record names it by `name`; nothing else is declared here.
export type SettingsComponentContribution = {
  app: string
  name: string
  component: () => Promise<unknown>
}

// An app's global acts: <module>/frontend/acts.js, whose default export is a list of acts. The
// shell imports it at idle and names each act `shell.<app>.<item>`.
export type ActsContribution = {
  app: string
  load: () => Promise<{ default?: unknown }>
}

// An app's field actions: <module>/frontend/field-actions.js, whose default export is a list of
// `FieldActionItem`. The record page imports it when a field that could hold an action draws.
export type FieldActionItem = ActionItem<string> & {
  fieldtype: string
  /** The record's quick action label; read at each build, so a getter can translate late. `label` is the field button's and the `⋯` row's. */
  quickActionLabel?: string
}

export type FieldActionsContribution = {
  app: string
  load: () => Promise<{ default?: unknown }>
}

// An app's shell hook: <module>/frontend/shell.js, whose `setup(shell)` the shell runs once per
// tab at idle, for a permitted user.
export type ShellHookContribution = {
  app: string
  load: () => Promise<{ setup?: unknown }>
}

export type Contributions = {
  doctypes: DoctypeContribution[]
  pages: PageContribution[]
  itemTypes: ItemTypeContribution[]
  viewTypes: ViewTypeContribution[]
  settings: SettingsComponentContribution[]
  acts: ActsContribution[]
  fieldActions: FieldActionsContribution[]
  shellHooks: ShellHookContribution[]
  replacements: ReplacementContribution[]
  pageScripts: PageScriptContribution[]
}
