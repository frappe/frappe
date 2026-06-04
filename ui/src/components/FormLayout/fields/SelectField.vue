<template>
  <Select
    v-model="value"
    :options="options"
    :label="field.label"
    :description="field.description"
    :placeholder="field.placeholder"
    :required="field.reqd"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Select } from 'frappe-ui'
import type { FieldComponentEmits, FieldComponentProps } from '../types'

const props = defineProps<FieldComponentProps>()
const emit = defineEmits<FieldComponentEmits>()

const value = computed<string | null>({
  get: () => props.modelValue ?? null,
  set: (v) => emit('update:modelValue', v),
})

/** Frappe `Select` options are a newline-joined string in meta. */
const options = computed(() =>
  (props.field.options ?? '').split('\n').map((o) => ({ label: o, value: o })),
)
</script>
