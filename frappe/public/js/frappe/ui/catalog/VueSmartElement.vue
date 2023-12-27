<script setup>
// @ts-check
import { markRaw } from "vue";

const props = defineProps({
	element: {
		type: [String, Object, Function, Promise],
		required: true,
	},
});

// NOTE: When providing a component, it must be included in the same bundle as the parent LinkCatalog component.
// Otherwise, this will cause issues with reactivity (because of the multiple Vue library imports).
</script>

<template>
	<template v-if="typeof element === 'string'">
		{{ element }}
	</template>
	<template v-if="Array.isArray(element)">
		<template v-for="item in element">
			<VueSmartElement :element="markRaw(item)" />
		</template>
	</template>
	<template v-else-if="element?.component">
		<component :is="element?.component" />
	</template>
	<template v-else-if="element?.html">
		<div v-html="element.html" />
	</template>
	<slot v-else-if="!element" name="fallback" />
	<slot v-else name="error" />
</template>
