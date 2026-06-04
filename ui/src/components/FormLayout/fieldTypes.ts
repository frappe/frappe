import type { Component } from 'vue'
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

export function registerFieldType(fieldtype: string, component: Component): void {
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

// One numeric control for all number types (no formatting yet — see Phase 6).
for (const t of ['Int', 'Float', 'Currency', 'Percent']) {
  registerFieldType(t, NumberField)
}

// One textarea for the multi-line text types.
for (const t of ['Small Text', 'Text', 'Long Text', 'Code']) {
  registerFieldType(t, TextareaField)
}

registerFieldType('Password', PasswordField)

registerFieldType(FALLBACK, TextField)
