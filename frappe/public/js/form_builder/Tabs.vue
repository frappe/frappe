<template>
	<div>
		<div class="tabs-container">
			<draggable
				v-show="layout.tabs.length > 1"
				class="tabs"
				v-model="layout.tabs"
				group="tabs"
				:animation="200"
			>
				<div
					class="tab"
					:class="{ 'active': active_tab == tab.df.name }"
					v-for="(tab, i) in layout.tabs"
					:key="i"
					@click="activate_tab(tab)"
					@dragstart="dragged = true"
					@dragend="dragged = false"
					@dragover="drag_over(tab)"
				>
					{{ tab.df.label }}
				</div>
			</draggable>
		</div>
		<div class="tabs-content">
			<div
				class="tab-content"
				v-for="(tab, i) in layout.tabs"
				:key="i"
				:active="active_tab == tab.df.name"
			>
				<draggable
					class="mb-4"
					v-model="tab.sections"
					group="sections"
					:animation="200"
				>
					<FormSection
						v-for="(section, i) in tab.sections"
						:key="i"
						:section="section"
						@add_section_above="add_section_above(section)"
					/>
				</draggable>
			</div>
		</div>
	</div>
</template>
<script>
import draggable from "vuedraggable";
import FormSection from "./FormSection.vue";
import { storeMixin } from "./store";

export default {
	name: 'Tabs',
	mixins: [storeMixin],
	components: {
		draggable,
		FormSection
	},
	data() {
		return {
			dragged: false,
			active_tab: this.$store.layout.tabs[0].df.name
		};
	},
	methods: {
		activate_tab(tab) {
			this.active_tab = tab.df.name;
			this.$store.selected_field = tab.df;
		},
		drag_over(tab) {
			!this.dragged && setTimeout(() => {
				this.active_tab = tab.df.name;
			}, 300);
		},
		add_section_above(section) {
			let sections = [];
			let current_tab = this.layout.tabs.find(tab => tab.df.name == this.active_tab);
			for (let _section of current_tab.sections) {
				if (_section === section) {
					sections.push({
						df: { fieldtype: "Section Break" },
						new_field: true,
						columns: [
							{ df: { fieldtype: "Column Break" }, new_field: true, fields: [] },
							{ df: { fieldtype: "Column Break" }, new_field: true, fields: [] }
						]
					});
				}
				sections.push(_section);
			}
			this.$set(current_tab, "sections", sections);
		}
	}
}
</script>

<style lang="scss" scoped>

.tabs-container {
	display: flex;
	align-items: center;
	border-bottom: 1px solid var(--border-color);

	.tabs {
		display: flex;
		margin-bottom: 0;
		padding-left: 5px;

		.tab {
			padding: var(--padding-md) 0;
			margin: 0 var(--margin-md);
			color: var(--text-muted);
			border-bottom: 1px solid var(--white);
			cursor: pointer;

			.tab-name {
				outline: none;
				border: none;
				width: fit-content;
			}

			&:hover {
				border-bottom: 1px solid var(--gray-300);
			}

			&.active {
				font-weight: 600;
				color: var(--text-color);
				border-bottom: 1px solid var(--primary);
			}
		}
	}
}
.tabs-content {
	padding: var(--padding-sm);

	.tab-content {
		display: none;

		&[active] {
			display: block;
		}
	}
}
</style>
