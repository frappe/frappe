<template>
  <TextInput
    type="number"
    :modelValue="value"
    :label="field.label"
    :description="field.description"
    :placeholder="field.placeholder"
    :required="field.reqd"
    :disabled="field.readOnly"
    @update:modelValue="onInput"
    @change="onCommit"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { TextInput } from 'frappe-ui'
import type { FieldComponentEmits, FieldComponentProps } from '../types'

const props = defineProps<FieldComponentProps>()
const emit = defineEmits<FieldComponentEmits>()

// No locale/precision formatting yet (deferred to Phase 6); round-trip a Number.
const value = computed<number | null>(() => props.modelValue ?? null)

// Live value while typing (keeps doc reactive); commit fires on blur.
function onInput(v: string) {
  emit('update:modelValue', v === '' ? null : Number(v))
}

function onCommit(e: Event) {
  const v = (e.target as HTMLInputElement).value
  emit('change', v === '' ? null : Number(v))
}
</script>
