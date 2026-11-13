<!-- The selected field's settings, in the look of frappe/crm#3419's PanelFieldSettings. Each change
     stages an edit at once; a text property stages when it is left or Enter is pressed. -->
<template>
	<PanelHeader
		:icon="typeIcon(currentType)"
		:title="field.label || field.fieldname"
		:subtitle="subtitle(canvas, field)"
		:remove-label="__('Remove field')"
		@remove="remove"
		@close="acts.perform('canvas.select', null)"
	/>
	<div v-if="errors.length || warning" class="flex flex-col gap-2 px-4 pb-3">
		<p v-for="error in errors" :key="error" class="text-p-sm text-ink-red-4" data-panel-error>
			{{ error }}
		</p>
		<Alert
			v-if="warning"
			theme="amber"
			:title="__('Mandatory in a conditional container')"
			:description="warning"
			data-panel-reqd-warning
		/>
	</div>
	<PanelSection :label="__('Field')">
		<PanelRow :label="__('Label')">
			<TextInput
				variant="ghost"
				:model-value="field.label ?? ''"
				:placeholder="field.fieldname"
				data-panel-label
				@change="set('label', text($event))"
			/>
		</PanelRow>
		<PanelRow :label="__('Type')" :box="false">
			<div class="rounded-4 hover:bg-surface-gray-2">
				<Dropdown :options="typeMenu" side="bottom" align="start">
					<button
						type="button"
						class="flex h-7 w-full items-center gap-2 rounded-4 px-2 text-left text-base text-ink-gray-8"
						data-panel-type
					>
						<span
							:class="[typeIcon(currentType), 'size-4 shrink-0 text-ink-gray-5']"
							aria-hidden="true"
						/>
						<span class="min-w-0 flex-1 truncate">{{ __(currentType) }}</span>
						<span
							class="lucide-chevron-down size-4 shrink-0 text-ink-gray-5"
							aria-hidden="true"
						/>
					</button>
				</Dropdown>
			</div>
			<p v-if="note" class="px-2 pb-1 pt-0.5 text-p-sm text-ink-gray-5" data-panel-type-note>
				{{ note }}
			</p>
		</PanelRow>
		<PanelRow v-if="field.fieldtype === 'Link'" :label="__('Links to')">
			<Combobox
				variant="ghost"
				:model-value="field.options ?? ''"
				:options="doctypes"
				:placeholder="__('Choose a DocType')"
				@update:model-value="set('options', String($event ?? ''))"
			/>
		</PanelRow>
		<PanelRow v-else-if="field.fieldtype === 'Select'" :label="__('Options')">
			<Textarea
				variant="ghost"
				:rows="3"
				class="!resize-none"
				:placeholder="__('One per line')"
				:model-value="field.options ?? ''"
				@change="set('options', text($event))"
			/>
		</PanelRow>
		<PanelRow v-else-if="field.fieldtype === 'Dynamic Link'" :label="__('DocType from')">
			<TextInput
				variant="ghost"
				:model-value="field.options ?? ''"
				:placeholder="__('A Link field to DocType')"
				@change="set('options', text($event))"
			/>
		</PanelRow>
		<PanelRow :label="__('Required')" :box="false">
			<div class="flex h-7 items-center px-2">
				<Switch
					size="sm"
					:model-value="Boolean(field.reqd)"
					@update:model-value="set('reqd', $event ? 1 : 0)"
				/>
			</div>
		</PanelRow>
		<PanelRow :label="__('Default')">
			<TextInput
				variant="ghost"
				:model-value="field.default ?? ''"
				:placeholder="__('None')"
				@change="set('default', text($event))"
			/>
		</PanelRow>
		<PanelRow v-if="field.fieldtype !== 'Check'" :label="__('Placeholder')">
			<TextInput
				variant="ghost"
				:model-value="field.placeholder ?? ''"
				:placeholder="__('Add placeholder…')"
				@change="set('placeholder', text($event))"
			/>
		</PanelRow>
		<PanelRow :label="__('Help text')">
			<Textarea
				variant="ghost"
				:rows="1"
				class="!min-h-7 !resize-none !py-1"
				:model-value="field.description ?? ''"
				:placeholder="__('Add help text…')"
				@change="set('description', text($event))"
			/>
		</PanelRow>
		<FieldnameRow :canvas="canvas" :field="field" />
	</PanelSection>
	<FieldPropertyGroups :canvas="canvas" :field="field" />
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { Alert, Combobox, Dropdown, Switch, Textarea, TextInput } from "frappe-ui";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { acts } from "@/acts/dispatcher";
import type { Addresses } from "@/addresses";
import { __ } from "@/i18n";
import { shellDialog } from "@/shell/dialog";
import type { DesignCanvas } from "./designCanvas";
import FieldnameRow from "./FieldnameRow.vue";
import {
	removeQuestion,
	reqdWarning,
	subtitle,
	typeChange,
	typeGroups,
	typeNote,
} from "./fieldPanel";
import FieldPropertyGroups from "./FieldPropertyGroups.vue";
import { typeIcon, typeName } from "./fieldtypes";
import PanelHeader from "./PanelHeader.vue";
import PanelRow from "./PanelRow.vue";
import PanelSection from "./PanelSection.vue";

const props = defineProps<{ canvas: DesignCanvas; field: RawMetaField }>();

const doctypes = inject<Addresses>("addresses")!.doctypes();
const currentType = computed(() => typeName(props.field.fieldtype, props.field.options));
const note = computed(() => typeNote(props.canvas, props.field));
const errors = computed(() => props.canvas.errorsAt("field", props.field.fieldname));
const warning = computed(() => reqdWarning(props.canvas, props.field.fieldname));

const typeMenu = computed(() => {
	const { groups, more } = typeGroups(props.canvas, props.field.fieldname);
	const option = ({ name, disabled }: { name: string; disabled: boolean }) => ({
		label: __(name),
		icon: typeIcon(name),
		disabled,
		onClick: () => pickType(name),
	});
	const menu: Record<string, unknown>[] = groups.map((group) => ({
		group: group.label,
		hideLabel: !group.label,
		options: group.types.map(option),
	}));
	if (!more.length) return menu;
	const submenu = more.map((group) => ({
		group: __(group.label),
		options: group.types.map(option),
	}));
	return [
		...menu,
		{
			group: "",
			hideLabel: true,
			options: [{ label: __("More types"), icon: "lucide-shapes", submenu }],
		},
	];
});

function set(property: string, value: unknown) {
	const current = (props.field as unknown as Record<string, unknown>)[property] ?? "";
	if (value === current) return;
	void acts.perform("fields.set_field_property", {
		fieldname: props.field.fieldname,
		property,
		value,
	});
}

function pickType(name: string) {
	if (name === currentType.value) return;
	void acts.perform("fields.set_field_property", {
		fieldname: props.field.fieldname,
		properties: typeChange(props.field, name),
	});
}

async function remove() {
	const { fieldname, label } = props.field;
	const question = removeQuestion(props.canvas, props.field);
	if (question) {
		const confirmed = await shellDialog().danger({
			title: __("Remove {0}?", [label || fieldname]),
			message: question,
			confirmLabel: __("Remove"),
		});
		if (!confirmed) return;
	}
	void acts.perform("fields.delete_field", { fieldname });
}

function text(event: Event) {
	return (event.target as HTMLInputElement).value.trim();
}
</script>
