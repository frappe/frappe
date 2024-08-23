<script setup>
import FieldProperties from "./FieldProperties.vue";
import { useStore } from "../store";
import { ref } from "vue";

let store = useStore();

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
	let screen_width = e.view.innerWidth;
	sidebar_width.value = screen_width - e.clientX - 90;

	if (sidebar_width.value < 16 * 16) {
		sidebar_width.value = 16 * 16;
	}
	if (sidebar_width.value > 24 * 16) {
		sidebar_width.value = 24 * 16;
	}
}
</script>

<template>
	<div
		:class="['sidebar-resizer', sidebar_resizing ? 'resizing' : '']"
		@mousedown="start_resize"
	/>
	<div class="sidebar-container" :style="{ width: `${sidebar_width}px` }">
		<FieldProperties v-if="store.form.selected_field" />
		<div class="default-state" v-else>
			<div
				class="actions"
				v-if="store.form.layout.tabs.length == 1 && !store.read_only && !store.doc.istable"
			>
				<button
					class="new-tab-btn btn btn-default btn-xs"
					:title="__('Add new tab')"
					@click="store.add_new_tab"
				>
					{{ __("Add tab") }}
				</button>
			</div>
			<div class="empty-state">
				<div>{{ __("Select a field to edit its properties.") }}</div>
			</div>
		</div>
	</div>
</template>

<style lang="scss" scoped>
.sidebar-resizer {
	position: absolute;
	top: 0;
	left: -5px;
	width: 5px;
	height: 100%;
	opacity: 0;
	background-color: var(--bg-gray);
	transition: opacity 0.2s ease;
	z-index: 4;
	cursor: col-resize;

	&:hover,
	&.resizing {
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

.default-state {
	display: flex;
	flex-direction: column;
	height: calc(100vh - 163px);

	.actions {
		padding: 5px;
		display: flex;
		justify-content: flex-end;
		border-bottom: 1px solid var(--border-color);
	}
	.empty-state {
		flex: 1;
		display: flex;
		justify-content: center;
		align-items: center;
		text-align: center;
		color: var(--disabled-text-color);
	}
}
</style>
