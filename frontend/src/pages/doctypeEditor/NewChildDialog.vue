<!-- "New child table…": the new child DocType's name, prefilled from the parent and the table's
     label. Nothing is written here: the parent's next save inserts it first. -->
<template>
	<Dialog
		v-model:open="isOpen"
		:title="__('New child table')"
		@update:open="!$event && emit('cancel')"
	>
		<div class="flex flex-col gap-4" data-new-child-dialog>
			<FormControl
				v-model="name"
				:label="__('Name')"
				:error="nameError"
				:description="__('A child DocType in {0}, saved with {1}.', [module, parent])"
				autofocus
			/>
		</div>
		<template #actions>
			<div class="flex justify-end gap-2">
				<Button :label="__('Cancel')" @click="emit('cancel')" />
				<Button
					variant="solid"
					:label="__('Create')"
					:disabled="!name.trim()"
					:loading="checking"
					@click="create"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { Button, Dialog, FormControl, toast } from "frappe-ui";
import { listDocuments } from "@framework/ui/api";
import { __ } from "@/i18n";
import { errorMessage } from "@/recordPage/errorMessage";
import { newChildName } from "./childSource";

const props = defineProps<{ parent: string; module: string; label: string }>();
const emit = defineEmits<{ create: [name: string]; cancel: [] }>();

const isOpen = ref(true);
const name = ref(newChildName(props.parent, props.label));
const taken = ref("");
const checking = ref(false);

const nameError = computed(() =>
	taken.value && taken.value === name.value.trim()
		? __("A DocType named {0} exists already", [taken.value])
		: undefined
);

async function create() {
	const wanted = name.value.trim();
	checking.value = true;
	try {
		const { data } = await listDocuments("DocType", {
			fields: ["name"],
			filters: { name: wanted },
			limit: 1,
		});
		taken.value = data.length ? wanted : "";
	} catch (error) {
		return void toast.error(errorMessage(error));
	} finally {
		checking.value = false;
	}
	if (!taken.value) emit("create", wanted);
}
</script>
