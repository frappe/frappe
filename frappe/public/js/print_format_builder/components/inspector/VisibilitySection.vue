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
import { computed, inject } from "vue";
import InspectorRow from "./InspectorRow.vue";

const props = defineProps(["modelValue"]);
defineEmits(["update:modelValue"]);

const store = inject("$store");
const previewDoc = computed(() => store.preview_doc.value);
const check = computed(() => store.condition_state(props.modelValue));
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
