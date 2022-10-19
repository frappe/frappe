<script setup>
import Section from "./Section.vue";
import draggable from "vuedraggable";
import { useStore } from "../store";
import { ref, computed } from "vue";

let store = useStore();

let layout = computed(() => store.layout);
let active_tab = ref(layout.value.tabs[0].df.name);

function activate_tab(tab) {
	active_tab.value = tab.df.name;
	store.selected_field = tab.df;
}
</script>

<template>
	<draggable
		v-show="layout.tabs.length > 1"
		class="tab-header"
		v-model="layout.tabs"
		group="tabs"
		:animation="200"
		item-key="id"
	>
		<template #item="{ element }">
			<div
				:class="['tab', active_tab == element.df.name ? 'active' : '']"
				@click="activate_tab(element)"
			>
				{{ element.df.label }}
			</div>
		</template>
	</draggable>

	<div class="tab-contents">
		<div
			class="tab-content"
			v-for="(tab, i) in layout.tabs"
			:key="i"
			:class="[active_tab == tab.df.name ? 'active' : '']"
		>
			<draggable
				:scroll-sensitivity="100"
				:force-fallback="true"
				class="tab-content-container"
				v-model="tab.sections"
				group="sections"
				:animation="200"
				item-key="id"
			>
				<template #item="{ element }">
					<Section :section="element" />
				</template>
			</draggable>
		</div>
	</div>
</template>

<style lang="scss" scoped>
.tab-header {
	display: flex;
	align-items: center;
	margin-bottom: 0;
	background-color: var(--fg-color);
	border-bottom: 1px solid var(--border-color);
	padding-left: var(--padding-xs);
	position: sticky;
	top: 0;
	z-index: 1;

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

.tab-contents {
	.tab-content {
		display: none;

		&.active {
			display: block;
		}
	}
}
</style>
