<!-- A Table field's "Child table": child DocTypes only, the parent's module first, and "New child
     table…" at its foot. A Table field with no child yet opens it by itself. -->
<template>
	<Combobox
		v-model:open="open"
		variant="ghost"
		side="bottom"
		align="start"
		class="w-full"
		:model-value="field.options || null"
		:options="groups"
		:disabled="locked"
		:placeholder="__('Choose a child table')"
		data-child-picker
		@update:model-value="pick"
	>
		<template #footer>
			<div class="border-t border-outline-gray-1 p-1">
				<button
					type="button"
					class="flex h-7 w-full items-center gap-2 rounded-4 px-2 text-left text-base text-ink-gray-8 hover:bg-surface-gray-3"
					data-new-child
					@click="startNew"
				>
					<span class="lucide-plus size-4 shrink-0 text-ink-gray-6" aria-hidden="true" />
					{{ __("New child table…") }}
				</button>
			</div>
		</template>
	</Combobox>
	<NewChildDialog
		v-if="naming"
		:parent="canvas.state.doctype"
		:module="canvas.state.module"
		:label="field.label ?? ''"
		@create="create"
		@cancel="naming = false"
	/>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, ref } from "vue";
import { Combobox, toast } from "frappe-ui";
import { listDocuments } from "@framework/ui/api";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import { errorMessage } from "@/recordPage/errorMessage";
import { CHILD_TABLES } from "./childTables";
import type { DesignCanvas } from "./designCanvas";
import NewChildDialog from "./NewChildDialog.vue";

interface ChildOption {
	name: string;
	module: string;
	custom: 0 | 1;
}

const props = defineProps<{ canvas: DesignCanvas; field: RawMetaField }>();

const tables = inject(CHILD_TABLES, null);
const open = ref(false);
const naming = ref(false);
const saved = ref<ChildOption[]>([]);
const locked = computed(
	() =>
		props.canvas.state.mode === "Customize" &&
		Boolean(props.canvas.savedName(props.field.fieldname))
);

const groups = computed(() => {
	const module = props.canvas.state.module;
	const added = (tables?.added() ?? []).map((name) => ({
		label: name,
		value: name,
		description: __("New, not saved"),
	}));
	const option = (one: ChildOption) => ({
		label: one.name,
		value: one.name,
		description: [one.module === module ? "" : one.module, one.custom ? __("Custom") : ""]
			.filter(Boolean)
			.join(" · "),
	});
	const mine = saved.value.filter((one) => one.module === module).map(option);
	const rest = saved.value.filter((one) => one.module !== module).map(option);
	return [
		{ group: module, options: [...added, ...mine] },
		{ group: __("Other modules"), options: rest },
	].filter((group) => group.options.length);
});

onMounted(async () => {
	if (!props.field.options && !props.canvas.savedName(props.field.fieldname))
		openWhenFocusSettles();
	try {
		const { data } = await listDocuments<ChildOption>("DocType", {
			fields: ["name", "module", "custom"],
			filters: { istable: 1 },
			order_by: "name asc",
			limit: 1000,
		});
		saved.value = data;
	} catch (error) {
		toast.error(errorMessage(error));
	}
});

/** A pick in the type menu hands focus back to its trigger as the menu closes, which would close this list. */
function openWhenFocusSettles() {
	if (!document.activeElement?.closest("[role='menu']")) return void (open.value = true);
	document.addEventListener("focusin", () => (open.value = true), { once: true });
}

function pick(value: unknown) {
	const name = String(value ?? "");
	if (!name || name === props.field.options) return;
	void acts.perform("fields.set_field_property", {
		fieldname: props.field.fieldname,
		property: "options",
		value: name,
	});
}

function startNew() {
	open.value = false;
	naming.value = true;
}

function create(name: string) {
	naming.value = false;
	void acts.perform("fields.add_child_table", { name, table_field: props.field.fieldname });
}
</script>
