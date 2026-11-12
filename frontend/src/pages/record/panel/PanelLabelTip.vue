<!-- What a panel label's tip says: the full label, then the field's description. -->
<template>
	<div class="max-w-56">
		<div>{{ field.label }}</div>
		<FieldDescription
			v-if="field.description"
			:html="field.description"
			class="block"
			:class="descriptionClass"
		/>
	</div>
</template>

<script setup lang="ts">
import { FieldDescription } from "@framework/ui/fields";
import type { FieldNode } from "@framework/ui/FormLayout/types";

defineProps<{ field: FieldNode; descriptionClass: string }>();
</script>
