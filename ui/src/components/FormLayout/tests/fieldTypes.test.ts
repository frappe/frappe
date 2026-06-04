import { describe, expect, it } from 'vitest'
import { defineComponent } from 'vue'
import { getFieldComponent, registerFieldType } from '../fieldTypes'
import CheckField from '../fields/CheckField.vue'
import DateField from '../fields/DateField.vue'
import DatetimeField from '../fields/DatetimeField.vue'
import LinkField from '../fields/LinkField.vue'
import NumberField from '../fields/NumberField.vue'
import PasswordField from '../fields/PasswordField.vue'
import SelectField from '../fields/SelectField.vue'
import TextField from '../fields/TextField.vue'
import TextareaField from '../fields/TextareaField.vue'
import TimeField from '../fields/TimeField.vue'

describe('fieldTypes registry', () => {
  it('resolves a registered fieldtype', () => {
    expect(getFieldComponent('Link')).toBe(LinkField)
  })

  it('resolves each new single-key fieldtype to its component', () => {
    expect(getFieldComponent('Select')).toBe(SelectField)
    expect(getFieldComponent('Check')).toBe(CheckField)
    expect(getFieldComponent('Date')).toBe(DateField)
    expect(getFieldComponent('Datetime')).toBe(DatetimeField)
    expect(getFieldComponent('Time')).toBe(TimeField)
    expect(getFieldComponent('Password')).toBe(PasswordField)
  })

  it('resolves all number fieldtypes to NumberField', () => {
    for (const t of ['Int', 'Float', 'Currency', 'Percent']) {
      expect(getFieldComponent(t)).toBe(NumberField)
    }
  })

  it('resolves all multi-line text fieldtypes to TextareaField', () => {
    for (const t of ['Small Text', 'Text', 'Long Text', 'Code']) {
      expect(getFieldComponent(t)).toBe(TextareaField)
    }
  })

  it('falls back to the text component for an unknown fieldtype', () => {
    expect(getFieldComponent('NotARealFieldtype')).toBe(TextField)
  })

  it('register overrides what resolve returns', () => {
    const custom = defineComponent({ name: 'Custom', render: () => null })
    registerFieldType('Link', custom)
    expect(getFieldComponent('Link')).toBe(custom)

    // restore so the override does not leak into other tests
    registerFieldType('Link', LinkField)
    expect(getFieldComponent('Link')).toBe(LinkField)
  })
})
