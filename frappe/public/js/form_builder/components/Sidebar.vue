<script setup>
import FieldTypes from "./FieldTypes.vue";
import FieldProperties from "./FieldProperties.vue";
import { ref, watch } from "vue";
import { useStore } from "../store";

let store = useStore();

let tab_titles = [__("Field Types"), __("Field Properties")];
let active_tab = ref(tab_titles[0]);
let sidebar_width = ref(272);
let sidebar_resizing = ref(false);

function start_resize() {
	$(document).on("mousemove", resize);
	$(document).on("mouseup", () => {
		$(".form-builder-container").removeClass("resizing");
		sidebar_resizing.value = false;
		$(document).off("mousemove", resize);
	});
}

function resize(e) {
	sidebar_resizing.value = true;
	$(".form-builder-container").addClass("resizing");
	sidebar_width.value = e.clientX - 90;

	if (sidebar_width.value < 16 * 16) {
		sidebar_width.value = 16 * 16;
	}
	if (sidebar_width.value > 24 * 16) {
		sidebar_width.value = 24 * 16;
	}
}

watch(
	() => store.form.selected_field,
	value => {
		active_tab.value = value ? tab_titles[1] : tab_titles[0];
	},
	{ deep: true }
);
</script>

<template>
	<div
		:class="['sidebar-resizer', sidebar_resizing ? 'resizing' : '']"
		@mousedown="start_resize"
	/>
	<div class="sidebar-container" :style="{ width: `${sidebar_width}px` }">
		<div class="tab-header">
			<div
				:class="['tab', active_tab == tab ? 'active' : '']"
				v-for="(tab, i) in tab_titles"
				:key="i"
				@click="active_tab = tab"
			>
				{{ tab }}
			</div>
		</div>
		<div :class="['tab-content', active_tab == tab_titles[0] ? 'active' : '']">
			<FieldTypes />
		</div>
		<div :class="['tab-content', active_tab == tab_titles[1] ? 'active' : '']">
			<FieldProperties />
		</div>
	</div>
</template>

<style lang="scss" scoped>
.sidebar-resizer {
	position: absolute;
	top: 0;
	right: -6px;
	width: 5px;
	height: 100%;
	opacity: 0;
	background-color: var(--bg-gray);
	transition: opacity 0.2s ease;
	z-index: 10;
	cursor: col-resize;

	&:hover, &.resizing {
		opacity: 1;
	}
}
.tab-header {
	display: flex;
	justify-content: space-between;
	align-items: center;
	padding: var(--padding-sm);
	background-color: var(--fg-color);
	border-top-left-radius: var(--border-radius);
	border-top-right-radius: var(--border-radius);

	.tab {
		display: flex;
		justify-content: center;
		align-items: center;
		width: 100%;
		height: 32px;
		background-color: var(--bg-gray);
		border-radius: var(--border-radius-md);
		border: 1px solid var(--dark-border-color);
		cursor: pointer;

		&:not(:first-child) {
			border-left: none;
			border-top-left-radius: 0;
			border-bottom-left-radius: 0;
		}

		&:first-child {
			border-top-right-radius: 0;
			border-bottom-right-radius: 0;
		}

		&.active {
			background-color: var(--fg-color);
		}
	}
}

.tab-content {
	display: none;
	&.active {
		display: block;
	}
}
</style>
