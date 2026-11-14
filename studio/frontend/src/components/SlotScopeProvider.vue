<template>
	<slot v-bind="attrs" />
</template>

<script setup lang="ts">
import { computed, inject, provide, useAttrs, type ComputedRef } from "vue"
import type { SlotScope } from "@/types"

// Renderless provider that pushes a scoped slot's props onto the scope stack
// so that blocks rendered inside the slot can reference them in expressions.
// Attrs are re-exposed as slot props because as-child triggers (Dropdown/Popover) merge their handlers onto this vnode as attrs
defineOptions({ inheritAttrs: false })

const props = defineProps<{
	scope: SlotScope
}>()

const attrs = useAttrs()

const parentScope = inject<ComputedRef<SlotScope> | null>("slotScope", null)
const scope = computed(() => ({ ...parentScope?.value, ...props.scope }))

provide("slotScope", scope)
</script>
