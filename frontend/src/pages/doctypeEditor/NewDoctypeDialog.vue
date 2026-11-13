<!-- `/doctype/new`: the four questions a new DocType needs before the editor opens on it. Nothing is
     written here: the editor's first save creates the DocType. -->
<template>
	<Dialog
		v-model:open="isOpen"
		:title="__('New DocType')"
		:dismissible="false"
		:show-close-button="false"
	>
		<div class="flex flex-col gap-4" data-new-doctype>
			<FormControl
				v-model="answers.name"
				:label="__('Name')"
				:placeholder="__('Delivery Route')"
				:error="nameError"
				autofocus
			/>
			<FormControl
				v-model="answers.module"
				type="combobox"
				:label="__('Module')"
				:options="modules"
			/>
			<FormControl v-model="kind" type="select" :label="__('Kind')" :options="kinds" />
			<FormControl
				v-model="answers.naming_rule"
				type="select"
				:label="__('Naming rule')"
				:options="namingRules"
			/>
		</div>
		<template #actions>
			<div class="flex justify-end gap-2">
				<Button :label="__('Cancel')" @click="emit('cancel')" />
				<Button
					variant="solid"
					:label="__('Create')"
					:disabled="!ready"
					:loading="checking"
					@click="create"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { Button, Dialog, FormControl, toast } from "frappe-ui";
import { listDocuments } from "@framework/ui/api";
import { __ } from "@/i18n";
import { errorMessage } from "@/recordPage/errorMessage";
import type { NewDoctype } from "./editorSource";

const emit = defineEmits<{ create: [answers: NewDoctype]; cancel: [] }>();

const isOpen = ref(true);
const answers = reactive({ name: "", module: "", naming_rule: "Set by user" });
const kind = ref("custom");
const modules = ref<{ label: string; value: string }[]>([]);
const taken = ref("");
const checking = ref(false);

const kinds = [
	{ label: __("Custom: kept on this site"), value: "custom" },
	{ label: __("Standard: saved to its app's files"), value: "standard" },
];
const namingRules = [
	"Set by user",
	"Autoincrement",
	"By fieldname",
	'By "Naming Series" field',
	"Random",
	"UUID",
].map((rule) => ({ label: __(rule), value: rule }));

const nameError = computed(() =>
	taken.value && taken.value === answers.name.trim()
		? __("A DocType named {0} exists already", [taken.value])
		: undefined
);
const ready = computed(() => !!answers.name.trim() && !!answers.module);

onMounted(async () => {
	try {
		const { data } = await listDocuments<{ name: string }>("Module Def", {
			fields: ["name"],
			order_by: "name asc",
			limit: 500,
		});
		modules.value = data.map((row) => ({ label: row.name, value: row.name }));
	} catch (error) {
		toast.error(errorMessage(error));
	}
});

async function create() {
	const name = answers.name.trim();
	checking.value = true;
	try {
		const { data } = await listDocuments("DocType", {
			fields: ["name"],
			filters: { name },
			limit: 1,
		});
		taken.value = data.length ? name : "";
	} catch (error) {
		return void toast.error(errorMessage(error));
	} finally {
		checking.value = false;
	}
	if (!taken.value) emit("create", { ...answers, name, custom: kind.value === "custom" });
}
</script>
