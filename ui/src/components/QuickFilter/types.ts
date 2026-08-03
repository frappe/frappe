/** Props for `<QuickFilter>`. It binds the same `Filter[]` `v-model:filters` the
 *  `Filter` control does, and (optionally) `v-model:fields` for the surfaced set. */
export interface QuickFilterProps {
  /** Doctype whose Meta drives the default surfaced quick-filter fields. */
  doctype: string;
}
