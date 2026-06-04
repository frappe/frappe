<template>
  <div class="field" :data-fieldname="field.fieldname" :data-fieldtype="field.fieldtype">
    <component
      :is="resolved"
      :field="field"
      :modelValue="doc[field.fieldname]"
      @update:modelValue="(value: any) => change(field.fieldname, value)"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, inject } from 'vue'
import { ChangeKey, DocKey, ResolveFieldKey } from './types'
import type { FieldMeta } from './types'

const props = defineProps<{ field: FieldMeta }>()

const doc = inject(DocKey)!
const change = inject(ChangeKey)!
const resolveField = inject(ResolveFieldKey)!

const resolved = computed(() => resolveField(props.field.fieldtype))
</script>
