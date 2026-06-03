<script setup>
import { computed } from "vue";
import { useLayoutBuilderStore, OVERRIDE_PROPS } from "../store";

const store = useLayoutBuilderStore();
const field = computed(() => store.selected_field);

// subset of OVERRIDE_PROPS valid for the current field
const applicable_props = computed(() => {
	if (!field.value) return [];
	const base = store.base_meta[field.value.fieldname] || {};
	const ft = base.fieldtype || "";
	return OVERRIDE_PROPS.filter((p) => {
		// reqd not meaningful for Check fields
		if (p.fieldname === "reqd" && ft === "Check") return false;
		return true;
	});
});

function on_change(prop, value) {
	if (!field.value) return;
	store.update_field(field.value.fieldname, prop, value);
}
</script>

<template>
	<div class="layout-builder-props" v-if="field">
		<div class="props-header">
			<div class="props-title">
				<strong>{{ field.label || field.fieldname }}</strong>
				<span class="text-muted small ms-1">({{ field.fieldname }})</span>
			</div>
			<button class="btn btn-xs btn-default" :title="__('Close')" @click="store.deselect()">
				<span v-html="frappe.utils.icon('remove', 'xs')" />
			</button>
		</div>

		<div class="props-body">
			<div v-for="prop in applicable_props" :key="prop.fieldname" class="prop-row">
				<!-- Check -->
				<template v-if="prop.fieldtype === 'Check'">
					<label class="prop-check-label">
						<input
							type="checkbox"
							:checked="!!field[prop.fieldname]"
							@change="on_change(prop.fieldname, $event.target.checked ? 1 : 0)"
						/>
						<span>{{ __(prop.label) }}</span>
					</label>
				</template>

				<!-- Small Text / multiline -->
				<template v-else-if="prop.fieldtype === 'Small Text'">
					<label class="prop-label">{{ __(prop.label) }}</label>
					<textarea
						class="form-control form-control-sm"
						rows="2"
						:value="field[prop.fieldname] || ''"
						:placeholder="prop.description ? __(prop.description) : ''"
						@change="on_change(prop.fieldname, $event.target.value)"
					/>
				</template>

				<!-- Data (default) -->
				<template v-else>
					<label class="prop-label">{{ __(prop.label) }}</label>
					<input
						type="text"
						class="form-control form-control-sm"
						:value="field[prop.fieldname] || ''"
						:placeholder="prop.description ? __(prop.description) : ''"
						@change="on_change(prop.fieldname, $event.target.value)"
					/>
				</template>
			</div>
		</div>
	</div>
</template>

<style lang="scss" scoped>
.layout-builder-props {
	display: flex;
	flex-direction: column;
	height: 100%;
}

.props-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 8px 12px;
	border-bottom: 1px solid var(--border-color);
	background: var(--fg-color);
	flex-shrink: 0;

	.props-title {
		font-size: 0.88em;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
}

.props-body {
	overflow-y: auto;
	padding: 10px 12px;
	flex: 1;
}

.prop-row {
	margin-bottom: 14px;
}

.prop-label {
	display: block;
	font-size: 0.8em;
	color: var(--text-muted);
	margin-bottom: 3px;
}

.prop-check-label {
	display: flex;
	align-items: center;
	gap: 6px;
	font-size: 0.85em;
	cursor: pointer;
	margin: 0;

	input {
		margin: 0;
		cursor: pointer;
	}
}
</style>
