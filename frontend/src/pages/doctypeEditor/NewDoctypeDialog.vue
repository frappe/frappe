<!-- `/doctype/new`: the four questions a new DocType needs before the editor opens on it, in a dialog
     over the DocType list; it closes with its answers. Nothing is written here: the editor's first
     save creates the DocType. -->
<template>
	<div class="flex flex-col gap-4" data-new-doctype>
		<FormControl
			v-model="answers.name"
			:label="__('Name')"
			:placeholder="__('Delivery Route')"
			:error="nameError"
			autofocus
		/>
		<div class="flex flex-col gap-1.5">
			<FormControl
				v-model="answers.module"
				type="combobox"
				:label="__('Module')"
				:options="modules"
				:placeholder="__('Choose a module')"
			/>
			<p class="text-sm text-ink-gray-6" data-module-hint>
				{{
					answers.module && answers.module === remembered
						? __("The last one you used.")
						: ""
				}}
				{{ __("Where its files go.") }}
			</p>
		</div>
		<FormControl v-model="kind" type="select" :label="__('Kind')" :options="kinds" />
		<FormControl
			v-model="answers.naming_rule"
			type="select"
			:label="__('Naming rule')"
			:options="namingRules"
		/>
		<div class="flex justify-end gap-2">
			<Button :label="__('Cancel')" @click="close(null)" />
			<Button
				variant="solid"
				:label="__('Continue')"
				:disabled="!ready"
				:loading="checking"
				@click="create"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { Button, FormControl, toast } from "frappe-ui";
import { listDocuments } from "@framework/ui/api";
import { __ } from "@/i18n";
import { errorMessage } from "@/recordPage/errorMessage";
import type { NewDoctype } from "./editorSource";

const props = defineProps<{
	initial?: Partial<NewDoctype>;
	/** The module the reader used last, which `initial` carries when nothing else named one. */
	remembered?: string;
	close: (answers: NewDoctype | null) => void;
}>();

const answers = reactive({
	name: props.initial?.name ?? "",
	module: props.initial?.module ?? "",
	naming_rule: props.initial?.naming_rule ?? "Set by user",
});
const kind = ref(props.initial?.custom === false ? "standard" : "custom");
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
		// A remembered or carried module that is gone from the site is no answer.
		if (!data.some((row) => row.name === answers.module)) answers.module = "";
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
	if (!taken.value) props.close({ ...answers, name, custom: kind.value === "custom" });
}
</script>
