<template>
	<div class="print-format-main" :style="rootStyles">
		<MarginText position="top_left" />
		<MarginText position="top_center" />
		<MarginText position="top_right" />
		<MarginText position="bottom_left" />
		<MarginText position="bottom_center" />
		<MarginText position="bottom_right" />

		<LetterHeadEditor type="Header" />
		<HTMLEditor
			:value="layout.header"
			@change="$set(layout, 'header', $event)"
			:button-label="__('Edit Header')"
		/>
		<draggable
			class="mb-4"
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
		<HTMLEditor
			:value="layout.footer"
			@change="$set(layout, 'footer', $event)"
			:button-label="__('Edit Footer')"
		/>
		<LetterHeadEditor type="Footer" />
	</div>
</template>

<script>
import draggable from "vuedraggable";
import HTMLEditor from "./HTMLEditor.vue";
import LetterHeadEditor from "./LetterHeadEditor.vue";
import MarginText from "./MarginText.vue";
import PrintFormatSection from "./PrintFormatSection.vue";
import { storeMixin } from "./store";

export default {
	name: "PrintFormat",
	mixins: [storeMixin],
	components: {
		draggable,
		PrintFormatSection,
		LetterHeadEditor,
		HTMLEditor,
		MarginText
	},
	computed: {
		rootStyles() {
			let {
				margin_top = 0,
				margin_bottom = 0,
				margin_left = 0,
				margin_right = 0
			} = this.print_format;
			return {
				padding: `${margin_top}mm ${margin_right}mm ${margin_bottom}mm ${margin_left}mm`,
				width: "210mm",
				minHeight: "297mm"
			};
		}
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
							{ label: "", fields: [] }
						]
					});
				}
				sections.push(_section);
			}
			this.$set(this.layout, "sections", sections);
		}
	}
};
</script>

<style scoped>
.print-format-main {
	position: relative;
	margin-right: auto;
	margin-left: auto;
	background-color: white;
	box-shadow: var(--shadow-lg);
	border-radius: var(--border-radius);
}
</style>
