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
			<TokenIcon v-if="isToken(item.value)" class="size-4 text-ink-gray-6" />
			<Avatar v-else :image="item.image" :label="item.label" size="sm" shape="circle" />
		</template>
		<template #item-label="{ item }">
			<div class="min-w-0">
				<div class="truncate text-ink-gray-9">{{ item.label }}</div>
				<div v-if="item.description" class="truncate text-p-sm text-ink-gray-5">
					{{ item.description }}
				</div>
			</div>
		</template>
	</MultiSelect>
</template>

<script setup lang="ts">
import { translate as __ } from "../../utils/translate";
import TokenIcon from "~icons/lucide/at-sign";
import { Avatar, MultiSelect, call } from "frappe-ui";
import { watchDebounced } from "@vueuse/core";
import { computed, ref, watch } from "vue";

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
// the users already picked, which a search page may not include, by user ID
const pickedOptions = ref({});
let requestId = 0;

const options = computed(() => {
	const values = new Map(props.modelValue.map(fallbackOption));
	Object.values(pickedOptions.value).forEach((option) => values.set(option.value, option));
	fetchedOptions.value.forEach((option) => values.set(option.value, option));
	return [...values.values()];
});

watchDebounced(query, loadUsers, { debounce: 250, immediate: true });
// the inspector reuses this picker across steps, so load whenever the picks change
watch(() => props.modelValue, loadPickedUsers, { immediate: true });

async function loadPickedUsers() {
	const names = props.modelValue.filter(
		(value) => !isToken(value) && !(value in pickedOptions.value)
	);
	if (!names.length) return;
	try {
		const users = await call("frappe.client.get_list", {
			doctype: "User",
			filters: { name: ["in", names] },
			fields: ["name", "full_name", "email", "user_image"],
			limit_page_length: names.length,
		});
		const loaded = Object.fromEntries(users.map((user) => [user.name, userOption(user)]));
		pickedOptions.value = { ...pickedOptions.value, ...loaded };
	} catch (error) {
		console.error("Unable to load the picked users", error);
	}
}

async function loadUsers(searchText) {
	const currentRequest = ++requestId;
	loading.value = true;
	try {
		const users = await call("frappe.automation_engine.api.get_param_options", {
			action_type: props.actionType,
			fieldname: props.fieldname,
			doctype: props.doctype,
			params: props.params,
			search_text: searchText,
		});
		if (currentRequest === requestId) fetchedOptions.value = users.map(userOption);
	} catch (error) {
		console.error("Unable to load automation assignees", error);
		if (currentRequest === requestId) fetchedOptions.value = [];
	} finally {
		if (currentRequest === requestId) loading.value = false;
	}
}

/** Tokens like @owner stand for whoever the run resolves them to. */
function isToken(value) {
	return String(value || "").startsWith("@");
}

function fallbackOption(value) {
	return [value, { label: value, value }];
}

function userOption(user) {
	return {
		label: user.full_name || user.email || user.name,
		value: user.name,
		description: user.full_name && user.email,
		image: user.user_image,
	};
}
</script>
