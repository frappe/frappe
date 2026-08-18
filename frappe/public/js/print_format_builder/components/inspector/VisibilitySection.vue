<template>
	<div class="pfb-visibility-body">
		<div class="pfb-insp-row--col" style="display: flex; flex-direction: column; gap: 6px">
			<label class="pfb-insp-label">{{ __("Show when") }}</label>
			<input
				class="pfb-insp-input"
				type="text"
				:placeholder="__('e.g. doc.status == \'Paid\'')"
				:value="modelValue"
				@input="$emit('update:modelValue', $event.target.value)"
			/>
			<div v-if="modelValue && modelValue.trim()" class="pfb-vis-status-row">
				<template v-if="previewDoc">
					<span class="es-badge" :data-theme="is_visible ? 'green' : 'gray'">
						<span
							class="pfb-vis-dot"
							:class="is_visible ? 'pfb-vis-dot--show' : 'pfb-vis-dot--hide'"
						></span>
						{{ is_visible ? __("Currently visible") : __("Currently hidden") }}
					</span>
				</template>
				<span v-else class="pfb-vis-hint-no-doc">
					{{ __("Load a document to see live status") }}
				</span>
			</div>
			<p class="pfb-insp-hint text-muted">
				{{ __("Leave blank to always show. Reference fields with") }}
				<code>doc.fieldname</code>.
			</p>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { evaluate_visible_if } from "../../utils";

const props = defineProps(["modelValue", "previewDoc"]);
defineEmits(["update:modelValue"]);

let is_visible = computed(() => evaluate_visible_if(props.modelValue, props.previewDoc));
</script>

<style scoped>
.pfb-visibility-body {
	padding: 4px 14px 12px;
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
