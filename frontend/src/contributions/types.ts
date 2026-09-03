import type { ItemRenderer } from "@/navigation/types"

// The complete list of what an app may contribute; if it is not here, an app cannot do it.

export type RecordHandlers = {
  actions?: { name: string; label: string; icon?: string; run: (page: unknown) => unknown }[]
  [key: string]: unknown
}

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

export type Contributions = {
  doctypes: DoctypeContribution[]
  pages: PageContribution[]
  itemTypes: ItemTypeContribution[]
}
