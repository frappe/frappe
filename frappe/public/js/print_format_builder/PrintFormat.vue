<template>
	<div class="print-format-main" :style="rootStyles">
		<div :style="page_number_style">{{ __("1 of 2") }}</div>

		<LetterHeadEditor type="Header" />
		<HTMLEditor
			:value="layout.header"
			@change="layout.header = $event"
			:button-label="__('Edit Header')"
		/>

		<draggable
			class="sections-container"
			v-model="layout.sections"
			group="sections"
			:animation="200"
			item-key="id"
			handle=".section-drag-handle"
			filter=".section-columns, .column, .field"
		>
			<template #item="{ element, index }">
				<div class="section-with-insert">
					<SectionInsert @insert="add_section_at(index)" />
					<PrintFormatSection :section="element" />
				</div>
			</template>
			<template #footer>
				<SectionInsert @insert="add_section_at(layout.sections.length)" />
			</template>
		</draggable>

		<HTMLEditor
			:value="layout.footer"
			@change="layout.footer = $event"
			:button-label="__('Edit Footer')"
		/>
		<HTMLEditor
			v-if="letterhead"
			:value="letterhead.footer"
			@change="update_letterhead_footer"
			:button-label="__('Edit Letter Head Footer')"
		/>
	</div>
</template>

<script setup>
import draggable from "vuedraggable";
import HTMLEditor from "./HTMLEditor.vue";
import LetterHeadEditor from "./LetterHeadEditor.vue";
import PrintFormatSection from "./PrintFormatSection.vue";
import SectionInsert from "./SectionInsert.vue";
import { useStore } from "./store";
import { computed, inject, watch } from "vue";

let { layout, letterhead, print_format } = useStore();
let store = inject("$store");

function add_section_at(index) {
	layout.value.sections.splice(index, 0, {
		label: "",
		columns: [{ label: "", fields: [] }],
	});
}

function update_letterhead_footer(val) {
	letterhead.value.footer = val;
}

let rootStyles = computed(() => {
	let {
		margin_top = 0,
		margin_bottom = 0,
		margin_left = 0,
		margin_right = 0,
	} = print_format.value;
	return {
		padding: `${margin_top}mm ${margin_right}mm ${margin_bottom}mm ${margin_left}mm`,
		width: "210mm",
		minHeight: "297mm",
	};
});

let page_number_style = computed(() => {
	let style = {
		position: "absolute",
		background: "white",
		padding: "4px",
		borderRadius: "var(--border-radius)",
		border: "1px solid var(--border-color)",
	};
	if (print_format.value.page_number.includes("Top")) {
		style.top = print_format.value.margin_top / 2 + "mm";
		style.transform = "translateY(-50%)";
	}
	if (print_format.value.page_number.includes("Left")) {
		style.left = print_format.value.margin_left + "mm";
	}
	if (print_format.value.page_number.includes("Right")) {
		style.right = print_format.value.margin_right + "mm";
	}
	if (print_format.value.page_number.includes("Bottom")) {
		style.bottom = print_format.value.margin_bottom / 2 + "mm";
		style.transform = "translateY(50%)";
	}
	if (print_format.value.page_number.includes("Center")) {
		style.left = "50%";
		style.transform += " translateX(-50%)";
	}
	if (print_format.value.page_number.includes("Hide")) {
		style.display = "none";
	}
	return style;
});

watch(layout, () => (store.dirty.value = true), { deep: true });
watch(print_format, () => (store.dirty.value = true), { deep: true });
</script>

<style scoped>
.print-format-main {
	position: relative;
	margin-right: auto;
	margin-left: auto;
	background-color: white;
	box-shadow: var(--shadow-lg);
}

.sections-container {
	margin-bottom: 1rem;
}

.section-with-insert {
	display: flex;
	flex-direction: column;
}
</style>
