<template>
	<MultiSelect
		:model-value="modelValue"
		:label="label"
		variant="outline"
		:options="options"
		:loading="loading"
		:placeholder="__('Select users')"
		:empty-text="__('No users found')"
		@update:model-value="$emit('update:modelValue', $event)"
		@update:query="query = $event"
	>
		<template #item-prefix="{ item }">
			<Icon
				v-if="isToken(item.value)"
				icon="lucide-at-sign"
				class="size-4 text-ink-gray-6"
			/>
			<Avatar v-else :label="item.label" size="sm" />
		</template>
		<template #item-label="{ item }">
			<div class="truncate text-ink-gray-9">{{ item.label }}</div>
		</template>
	</MultiSelect>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { watchDebounced } from "@vueuse/core";
import { Avatar, Icon, MultiSelect } from "frappe-ui";
import { runMethod } from "@framework/ui/api";

const props = defineProps({
	modelValue: { type: Array, default: () => [] },
	actionType: { type: String, required: true },
	fieldname: { type: String, required: true },
	doctype: { type: String, default: "" },
	params: { type: String, default: "{}" },
	label: { type: String, default: "" },
});

defineEmits(["update:modelValue"]);

const query = ref("");
const loading = ref(false);
const fetchedOptions = ref([]);
let requestId = 0;

// A chosen user stays listed while the search has not returned it.
const options = computed(() => {
	const values = new Map(props.modelValue.map((value) => [value, { label: value, value }]));
	fetchedOptions.value.forEach((option) => values.set(option.value, option));
	return [...values.values()];
});

watchDebounced(query, loadUsers, { debounce: 250, immediate: true });
// The candidate users depend on the DocType and on sibling params, so they are asked again.
watch(
	() => [props.doctype, props.params],
	() => loadUsers(query.value)
);

async function loadUsers(searchText) {
	const request = ++requestId;
	loading.value = true;
	try {
		const { data } = await runMethod(
			"frappe.automation_engine.api.get_param_options",
			{
				action_type: props.actionType,
				fieldname: props.fieldname,
				doctype: props.doctype,
				params: props.params,
				search_text: searchText,
			},
			{ http: "GET" }
		);
		if (request === requestId) fetchedOptions.value = data.map(userOption);
	} catch {
		if (request === requestId) fetchedOptions.value = [];
	} finally {
		if (request === requestId) loading.value = false;
	}
}

/** Tokens like @owner stand for whoever the run resolves them to. */
function isToken(value) {
	return String(value || "").startsWith("@");
}

function userOption(user) {
	return { label: user.full_name || user.name, value: user.name };
}
</script>
