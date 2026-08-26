// The public contribution surface -- the COMPLETE list of what an app may contribute.
// If it is not in this file, an app cannot do it. That closure is charter item 1:
// there is no optional escape hatch to route around, because that is exactly how
// desk v1's Client Script tier rotted.

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
  // 1. Customize your own doctype's record page.
  //    <module>/doctype/<scrubbed>/frontend/record.js
  | { kind: 'record'; app: string; doctype: string; handlers: RecordHandlers }
  // 2. Customize your own doctype's list.
  //    <module>/doctype/<scrubbed>/frontend/list.js
  | { kind: 'list'; app: string; doctype: string; handlers: ListHandlers }
  // 3. Customize a FOREIGN doctype. <module>/custom/<scrubbed>/record.js
  //    Same two kinds; only the folder differs. Applies globally, so customizing
  //    Contact does NOT move Contact into your prefix (#42068).
  | { kind: 'custom'; app: string; doctype: string; handlers: RecordHandlers }

// 4. Add a genuinely new page. <module>/frontend/pages/<slug>.js -- see
//    PageContribution above.
//
// NOT contributable, each for a decided reason:
//   - a route table          -> generated from doctypes; pages are flat files
//   - a doctype opt-out      -> it hides nothing and would be misread as a
//                               permission control (#42068)
//   - shell chrome, incl. every error state -> the shell owns it (#42072)
//   - a vite plugin or config -> the framework owns the build (#42069)
//   - a boot key, from JS    -> boot is Python (#42070)
//
// Four entries, three of them the same mechanism pointed at different folders. That
// is the test of whether the seam is small enough.

export type Contributions = {
  doctypes: DoctypeContribution[]
  pages: PageContribution[]
}
