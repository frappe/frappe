<template>
	<textarea
		class="form-control form-control-sm pfb-typst-input"
		:placeholder="'#text(weight: \'bold\')[Hello]'"
		spellcheck="false"
		rows="8"
		:value="selected_field.typst || ''"
		@input="(e) => (selected_field.typst = e.target.value)"
	></textarea>
	<div class="pfb-insp-hint text-muted">{{ hint }}</div>
</template>

<script setup>
import { useSelectedField } from "./useSelectedField";

const { selected_field } = useSelectedField();
const hint = __(
	"Write Typst here. Use {0} for values from the document. Check the PDF preview to see the result.",
	["{{ doc.field_name }}"]
);
</script>
