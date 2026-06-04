<template>
  <TextInput
    type="number"
    :modelValue="value"
    :label="field.label"
    :description="field.description"
    :placeholder="field.placeholder"
    :required="field.reqd"
    @update:modelValue="onInput"
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

function onInput(v: string) {
  emit('update:modelValue', v === '' ? null : Number(v))
}
</script>
