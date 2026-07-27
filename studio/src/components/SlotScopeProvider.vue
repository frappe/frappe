<template>
	<slot />
</template>

<script setup lang="ts">
import { computed, inject, provide, type ComputedRef } from "vue"
import type { SlotScope } from "@/types"

// Renderless provider that pushes a scoped slot's props onto the scope stack
// so that blocks rendered inside the slot can reference them in expressions.
const props = defineProps<{
	scope: SlotScope
}>()

const parentScope = inject<ComputedRef<SlotScope> | null>("slotScope", null)
const scope = computed(() => ({ ...parentScope?.value, ...props.scope }))

provide("slotScope", scope)
</script>
