import type { Component } from 'vue'
import { setScoped } from './scopedRegistry'
import CheckField from './fields/CheckField.vue'
import DateField from './fields/DateField.vue'
import DatetimeField from './fields/DatetimeField.vue'
import LinkField from './fields/LinkField.vue'
import NumberField from './fields/NumberField.vue'
import PasswordField from './fields/PasswordField.vue'
import SelectField from './fields/SelectField.vue'
import TextField from './fields/TextField.vue'
import TextareaField from './fields/TextareaField.vue'
import TimeField from './fields/TimeField.vue'

/** Process-global fieldtype → component registry. */
const registry = new Map<string, Component>()

const FALLBACK = '__fallback__'

export interface RegisterFieldTypeOptions {
  /**
   * `true` (default): register **globally** for the process — the registration
   * persists until overwritten. This is how apps install their fields once at
   * startup.
   *
   * `false`: register **scoped** to the current Vue effect scope (a component's
   * `setup`). The previous mapping is snapshotted and **automatically restored**
   * when that scope is disposed (the component unmounts). Use this for an override
   * that must not leak to the rest of the app — e.g. a story/demo, or a screen
   * that swaps a field only while it is open. Must be called synchronously in
   * `setup` (so it is in place before child fields render); if there is no active
   * scope to tie cleanup to, it falls back to a global registration and warns.
   */
  global?: boolean
}

export function registerFieldType(
  fieldtype: string,
  component: Component,
  options: RegisterFieldTypeOptions = {},
): void {
  const { global = true } = options

  // Scoped: snapshot + auto-restore on the current component's unmount.
  if (!global && setScoped(registry, fieldtype, component)) return

  if (!global) {
    console.warn(
      `[FormLayout] registerFieldType('${fieldtype}', …, { global: false }) was ` +
        `called outside a Vue effect scope (component setup), so there is nothing ` +
        `to auto-revert on. Registered globally instead.`,
    )
  }
  registry.set(fieldtype, component)
}

export function getFieldComponent(fieldtype: string): Component {
  return registry.get(fieldtype) ?? registry.get(FALLBACK)!
}

registerFieldType('Link', LinkField)
registerFieldType('Select', SelectField)
registerFieldType('Check', CheckField)
registerFieldType('Date', DateField)
registerFieldType('Datetime', DatetimeField)
registerFieldType('Time', TimeField)

// One numeric control for all number types; it formats per fieldtype (locale
// grouping, precision, currency symbol, percent) with lib defaults. Apps wanting
// site-accurate settings register their own field (see formatNumber.ts).
for (const t of ['Int', 'Float', 'Currency', 'Percent']) {
  registerFieldType(t, NumberField)
}

// One textarea for the multi-line text types.
for (const t of ['Small Text', 'Text', 'Long Text', 'Code']) {
  registerFieldType(t, TextareaField)
}

registerFieldType('Password', PasswordField)

// `Read Only` renders as a disabled text box (buildLayoutFromMeta marks it
// `readOnly: true`, which TextField honours via `:disabled`).
registerFieldType('Read Only', TextField)

registerFieldType(FALLBACK, TextField)
