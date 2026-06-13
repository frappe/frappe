<script setup>
import { ref, watch, onMounted } from "vue";
import draggable from "vuedraggable";
import FieldRow from "./FieldRow.vue";
import FieldProperties from "./FieldProperties.vue";
import { useLayoutBuilderStore } from "../store";
import { onClickOutside } from "@vueuse/core";

const store = useLayoutBuilderStore();
const container = ref(null);

onClickOutside(container, () => store.deselect());

/** vuedraggable v-model — mirrors store.fields */
const drag_fields = ref([]);

onMounted(() => {
	drag_fields.value = store.fields;
});

watch(
	() => store.fields,
	(val) => {
		drag_fields.value = val;
	},
	{ deep: false }
);

function on_drag_end() {
	const new_order = drag_fields.value.map((f) => f.fieldname);
	store.reorder(new_order);
}
</script>

<template>
	<div class="lb-container" ref="container">
		<!-- Field list panel -->
		<div class="lb-main">
			<div v-if="!drag_fields.length" class="lb-empty">
				<p class="text-muted">
					{{ __("No fields yet. Set a Document Type and click Sync Fields.") }}
				</p>
			</div>

			<draggable
				v-else
				v-model="drag_fields"
				item-key="fieldname"
				handle=".lb-drag-handle"
				animation="150"
				ghost-class="lb-ghost"
				chosen-class="lb-chosen"
				:delay="is_touch_screen_device() ? 200 : 0"
				@end="on_drag_end"
			>
				<template #item="{ element }">
					<FieldRow :field="element" />
				</template>
			</draggable>
		</div>

		<!-- Properties panel -->
		<div class="lb-sidebar" :class="{ 'lb-sidebar-visible': !!store.selected_field }">
			<FieldProperties v-if="store.selected_field" />
			<div v-else class="lb-sidebar-placeholder">
				<span v-html="frappe.utils.icon('es-line-settings', 'lg')" />
				<p class="text-muted mt-2">
					{{ __("Click a field to edit its layout overrides") }}
				</p>
			</div>
		</div>
	</div>
</template>

<style lang="scss" scoped>
.lb-container {
	display: flex;
	border: 1px solid var(--border-color);
	border-radius: var(--border-radius);
	overflow: hidden;
	min-height: 200px;
}

.lb-main {
	flex: 1;
	overflow-y: auto;
	border-right: 1px solid var(--border-color);
}

.lb-empty {
	padding: 24px;
	text-align: center;
}

.lb-ghost {
	opacity: 0.4;
	background: var(--yellow-50) !important;
}

.lb-chosen {
	box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
}

.lb-sidebar {
	width: 0;
	overflow: hidden;
	transition: width 0.2s ease;
	background: var(--fg-color);
	display: flex;
	flex-direction: column;

	&.lb-sidebar-visible {
		width: 280px;
	}
}

.lb-sidebar-placeholder {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 24px;
	height: 100%;
	text-align: center;
	font-size: 0.85em;
}
</style>
