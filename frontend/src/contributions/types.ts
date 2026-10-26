import type { Component } from "vue"
import type { ItemRenderer } from "@/navigation/types"

// The complete list of what an app may contribute; if it is not here, an app cannot do it.

type RecordHandler = (page: object, row?: object) => unknown

export type RecordHandlers = Record<string, RecordHandler | Record<string, RecordHandler>>

export type ListHandlers = {
  columns?: { fieldname: string; width?: number }[]
  [key: string]: unknown
}

export type PageContribution = {
  app: string
  slug: string
  title?: string
  component: () => Promise<unknown>
}

export type DoctypeContribution =
  // Your own doctype's record page: <module>/doctype/<scrubbed>/frontend/record.js
  | { kind: 'record'; app: string; doctype: string; handlers: RecordHandlers }
  // Your own doctype's list: <module>/doctype/<scrubbed>/frontend/list.js
  | { kind: 'list'; app: string; doctype: string; handlers: ListHandlers }
  // A foreign doctype: <module>/custom/<scrubbed>/record.js. Applies globally; it does not
  // move the doctype into your prefix.
  | { kind: 'custom'; app: string; doctype: string; handlers: RecordHandlers }

// A page in place of a doctype's record or list page: <module>/doctype/<scrubbed>/frontend/
// pages/<name>.js, named in pages.json beside it; the same under <module>/custom/<scrubbed>/.
export type ReplacementContribution = {
  app: string
  doctype: string
  key: 'record' | 'list'
  foreign: boolean
  title?: string
  component: () => Promise<unknown>
}

export type StandardPages = {
  /** The page at a main list or record address: the declared page, else the standard one. */
  main: Component
  home: () => Promise<unknown>
  module: () => Promise<unknown>
  list: () => Promise<unknown>
  record: () => Promise<unknown>
  newRecord: () => Promise<unknown>
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

// A settings block's component: <module>/frontend/settings/<name>.vue, loaded when its pane
// opens. The app's `Settings Dialog` record names it by `name`; nothing else is declared here.
export type SettingsComponentContribution = {
  app: string
  name: string
  component: () => Promise<unknown>
}

export type Contributions = {
  doctypes: DoctypeContribution[]
  pages: PageContribution[]
  itemTypes: ItemTypeContribution[]
  settings: SettingsComponentContribution[]
  replacements: ReplacementContribution[]
}
