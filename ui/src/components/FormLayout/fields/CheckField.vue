<template>
  <Checkbox
    v-model="value"
    :label="field.label"
    :description="field.description"
    :required="field.reqd"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Checkbox } from 'frappe-ui'
import type { FieldComponentEmits, FieldComponentProps } from '../types'

const props = defineProps<FieldComponentProps>()
const emit = defineEmits<FieldComponentEmits>()

// Backends send `0 | 1`; adapt at the edge and emit a clean boolean.
const value = computed<boolean>({
  get: () => Boolean(props.modelValue),
  set: (v) => emit('update:modelValue', v),
})
</script>
