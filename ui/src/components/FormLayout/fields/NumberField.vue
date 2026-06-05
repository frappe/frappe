<template>
  <TextInput
    ref="inputRef"
    type="text"
    :modelValue="display"
    :label="field.label"
    :description="field.description"
    :placeholder="field.placeholder"
    :required="field.reqd"
    :disabled="field.readOnly"
    @focus="onFocus"
    @blur="focused = false"
    @update:modelValue="onInput"
    @change="onChange"
  />
</template>

<script setup lang="ts">
import { computed, inject, nextTick, ref } from 'vue'
import { TextInput } from 'frappe-ui'
import { DocKey } from '../types'
import type { FieldComponentEmits, FieldComponentProps } from '../types'
import { flt, formatField } from '../formatNumber'
import { getFormatDefaults } from '../formatDefaults'

const props = defineProps<FieldComponentProps>()
const emit = defineEmits<FieldComponentEmits>()

// Format-on-blur / raw-on-focus (mirrors Frappe's FormattedInput): we override
// *only* the displayed string — formatted when not editing, raw while editing.
// Everything else (commit on blur/Enter, only-when-changed) rides on TextInput's
// native `@change`, exactly like TextField. The input is `type="text"` because
// grouped strings aren't a valid `type="number"` value.
const focused = ref(false)
const draft = ref('')
const inputRef = ref<{ el?: HTMLInputElement } | null>(null)

// Available so a Currency field can resolve its currency code from a sibling
// field on the doc (Frappe's `options`-points-to-a-field convention). Optional:
// the field renders fine standalone (no doc provided).
const doc = inject(DocKey, null)

const display = computed(() =>
  focused.value ? draft.value : formatted(props.modelValue),
)

/**
 * Currency code for a Currency field. Precedence: the field's `options` (a
 * sibling field on the doc, else a literal code) → the site default currency
 * (`getFormatDefaults`, framework data). Per-field meta wins over the site default.
 */
function resolveCurrency(): string | undefined {
  const opt = props.field.options
  if (opt) {
    const fromDoc = doc?.value?.[opt]
    if (typeof fromDoc === 'string' && fromDoc) return fromDoc
    if (!doc?.value?.[opt]) return opt // literal code on the field
  }
  const sysCurrency = getFormatDefaults().currency
  return sysCurrency ?? undefined
}

/**
 * Resolve the decimal places: per-field `precision` (meta) wins; else the
 * matching site default (`currency_precision` for Currency, `float_precision`
 * for Float/Percent); else `undefined`, letting the pure util derive it from the
 * number format (and force 0 for Int).
 */
function resolvePrecision(fieldtype: string | undefined): number | undefined {
  // Int has no precision — it renders as a plain integer (see formatField).
  if (fieldtype === 'Int') return undefined
  if (props.field.precision != null) return props.field.precision
  const d = getFormatDefaults()
  const sys = fieldtype === 'Currency' ? d.currency_precision : d.float_precision
  if (sys == null || sys === '') return undefined
  const n = Number(sys)
  return Number.isNaN(n) ? undefined : n
}

function formatted(value: any): string {
  const { fieldtype } = props.field
  const defaults = getFormatDefaults()
  // Currency is the only type needing the doc; resolve it here (Vue-coupled) and
  // hand a plain code to the pure formatter. Site number_format / rounding flow
  // in from the resolved framework defaults; per-field meta wins on precision.
  const currency = fieldtype === 'Currency' ? resolveCurrency() : undefined
  return formatField(value, {
    fieldtype,
    precision: resolvePrecision(fieldtype),
    currency,
    numberFormat: defaults.number_format,
    roundingMethod: defaults.rounding_method,
  })
}

function parse(s: string): number | null {
  if (s === '') return null
  const defaults = getFormatDefaults()
  return flt(s, {
    numberFormat: defaults.number_format,
    roundingMethod: defaults.rounding_method,
  })
}

// Switch to the raw, editable value while focused (preserve exact keystrokes),
// and select it all so a fresh entry overwrites — matches Frappe's FormattedInput.
function onFocus() {
  focused.value = true
  draft.value = props.modelValue == null ? '' : String(props.modelValue)
  nextTick(() => inputRef.value?.el?.select())
}

// Live value while typing — keeps `doc` and conditional visibility reactive.
function onInput(v: string) {
  draft.value = v
  emit('update:modelValue', parse(v))
}

// Commit — the input's native `change` (blur or Enter, only when the value
// changed). Same funnel TextField uses; we just parse the raw string back.
function onChange(e: Event) {
  emit('change', parse((e.target as HTMLInputElement).value))
}
</script>
