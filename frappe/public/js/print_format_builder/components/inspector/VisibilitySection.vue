<template>
	<div class="pfb-visibility-body">
		<InspectorRow :label="__('Condition')" stacked>
			<input
				class="pfb-insp-input"
				type="text"
				:placeholder="__('e.g. doc.status == \'Paid\'')"
				:value="modelValue"
				@input="$emit('update:modelValue', $event.target.value)"
			/>
			<div v-if="modelValue && modelValue.trim()" class="pfb-vis-status-row">
				<template v-if="previewDoc">
					<span
						v-if="check.error"
						class="es-badge"
						data-theme="orange"
						:title="check.error"
					>
						{{ __("Can't check this condition") }}
					</span>
					<span
						v-else-if="check.visible != null"
						class="es-badge"
						:data-theme="check.visible ? 'green' : 'gray'"
					>
						<span
							class="pfb-vis-dot"
							:class="check.visible ? 'pfb-vis-dot--show' : 'pfb-vis-dot--hide'"
						></span>
						{{ check.visible ? __("Currently visible") : __("Currently hidden") }}
					</span>
				</template>
				<span v-else class="pfb-vis-hint-no-doc">
					{{ __("Load a document to see live status") }}
				</span>
			</div>
		</InspectorRow>
	</div>
</template>

<script setup>
import { ref, watch } from "vue";
import InspectorRow from "./InspectorRow.vue";

const props = defineProps(["modelValue", "previewDoc"]);
defineEmits(["update:modelValue"]);

let check = ref({});
let seq = 0;
const run_check = frappe.utils.debounce(() => {
	const condition = (props.modelValue || "").trim();
	const doc = props.previewDoc;
	if (!condition || !doc?.name) return (check.value = {});
	const mine = ++seq;
	frappe
		.call("frappe.utils.print_format_generator.check_condition", {
			doctype: doc.doctype,
			name: doc.name,
			condition,
		})
		.then((r) => mine === seq && (check.value = r.message || {}));
}, 400);
watch([() => props.modelValue, () => props.previewDoc?.name], run_check, { immediate: true });
</script>

<style scoped>
.pfb-visibility-body {
	padding: 4px 16px 16px;
}

.pfb-vis-status-row {
	display: flex;
	align-items: center;
	gap: 6px;
}

.pfb-vis-dot {
	width: 6px;
	height: 6px;
	border-radius: 50%;
	flex-shrink: 0;
}

.pfb-vis-dot--show {
	background: var(--green-500);
}

.pfb-vis-dot--hide {
	background: var(--gray-400);
}

.pfb-vis-hint-no-doc {
	font-size: var(--text-xs);
	color: var(--text-muted);
}
</style>
