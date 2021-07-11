<template>
	<div class="print-format-main" :style="rootStyles">
		<draggable
			v-model="layout.sections"
			group="sections"
			filter=".section-columns, .column, .field"
			:animation="200"
		>
			<PrintFormatSection
				v-for="(section, i) in layout.sections"
				:key="i"
				:section="section"
				@add_section_above="add_section_above(section)"
			/>
		</draggable>
	</div>
</template>

<script>
import draggable from "vuedraggable";
import PrintFormatSection from "./PrintFormatSection.vue";

export default {
	name: "PrintFormat",
	props: ["print_format", "meta", "layout"],
	components: {
		draggable,
		PrintFormatSection,
	},
	computed: {
		rootStyles() {
			let {
				margin_top = 0,
				margin_bottom = 0,
				margin_left = 0,
				margin_right = 0,
			} = this.print_format;
			return {
				padding: `${margin_top}mm ${margin_right}mm ${margin_bottom}mm ${margin_left}mm`,
				width: "210mm",
				minHeight: "297mm",
			};
		},
	},
	methods: {
		add_section_above(section) {
			let sections = [];
			for (let _section of this.layout.sections) {
				if (_section === section) {
					sections.push({
						label: "",
						columns: [
							{ label: "", fields: [] },
							{ label: "", fields: [] },
						],
					});
				}
				sections.push(_section);
			}
			this.$set(this.layout, "sections", sections);
		},
	},
};
</script>

<style scoped>
.print-format-main {
	margin-left: auto;
	background-color: white;
	box-shadow: var(--shadow-lg);
	border-radius: var(--border-radius);
}
</style>