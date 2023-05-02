<script setup>
import { computed } from "vue";
import { useStore } from "../store";

let store = useStore();

let properties = computed(() => {
	return store.workflowfields.filter(df => {
		if (in_list(["states", "transitions", "workflow_data", "workflow_name"], df.fieldname)) {
			return false;
		}
		return true;
	});
});
</script>

<template>
	<div class="properties">
		<div class="control-data">
			<div v-if="store.workflow_doc">
				<div class="field" v-for="df in properties" :key="df.name">
					<component
						:is="df.fieldtype.replace(' ', '') + 'Control'"
						:df="df"
						:value="store.workflow_doc[df.fieldname]"
						v-model="store.workflow_doc[df.fieldname]"
						:data-fieldname="df.fieldname"
						:data-fieldtype="df.fieldtype"
					/>
				</div>
			</div>
		</div>
	</div>
</template>

<style lang="scss" scoped>
.control-data {
	height: calc(100vh - 210px);
	overflow-y: auto;
	padding: 8px;

	.field {
		margin: 5px;
		margin-top: 0;
		margin-bottom: 1rem;

		:deep(.form-control:disabled) {
			color: var(--disabled-text-color);
			background-color: var(--disabled-control-bg);
			cursor: default;
		}
		:deep(.description) {
			font-size: var(--text-sm);
			color: var(--text-muted);
		}
	}
}
</style>
