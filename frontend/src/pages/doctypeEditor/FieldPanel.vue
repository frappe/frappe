<!-- The selected field's settings, in the look of frappe/crm#3419's PanelFieldSettings. Each change
     stages an edit at once; a text property stages when it is left or Enter is pressed. -->
<template>
	<PanelHeader
		:icon="typeIcon(currentType)"
		:title="field.label || field.fieldname"
		:subtitle="subtitle(canvas, field)"
		:remove-label="removal.label"
		:remove-icon="removal.icon"
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
		<PanelRow :label="__('Label')" v-bind="mark('label')">
			<TextInput
				variant="ghost"
				:model-value="field.label ?? ''"
				:placeholder="field.fieldname"
				data-panel-label
				@change="set('label', text($event))"
			/>
		</PanelRow>
		<PanelRow :label="__('Type')" :box="false" v-bind="mark('fieldtype')">
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
		<PanelRow v-if="anchor !== undefined" :label="__('Placed after')" :box="false">
			<div class="flex min-h-7 flex-col justify-center px-2" data-panel-anchor>
				<p class="flex h-7 items-center truncate text-base text-ink-gray-8">
					{{ anchor ? anchor.label || anchor.fieldname : __("The start of the form") }}
				</p>
				<p class="pb-1 text-p-sm text-ink-gray-5">
					{{
						__("Drag it to move it. It keeps this place when {0} adds fields.", [
							appTitle,
						])
					}}
				</p>
			</div>
		</PanelRow>
		<PanelRow
			v-if="field.fieldtype === 'Link'"
			:label="__('Links to')"
			v-bind="mark('options')"
		>
			<Combobox
				variant="ghost"
				:model-value="field.options ?? ''"
				:options="doctypes"
				:placeholder="__('Choose a DocType')"
				@update:model-value="setTarget(String($event ?? ''))"
			/>
		</PanelRow>
		<TableFieldRows v-else-if="field.fieldtype === 'Table'" :canvas="canvas" :field="field" />
		<PanelRow
			v-else-if="field.fieldtype === 'Select'"
			:label="__('Options')"
			v-bind="mark('options')"
		>
			<Textarea
				variant="ghost"
				:rows="3"
				class="!resize-none"
				:placeholder="__('One per line')"
				:model-value="field.options ?? ''"
				@change="set('options', text($event))"
			/>
		</PanelRow>
		<PanelRow
			v-else-if="field.fieldtype === 'Dynamic Link'"
			:label="__('DocType from')"
			v-bind="mark('options')"
		>
			<TextInput
				variant="ghost"
				:model-value="field.options ?? ''"
				:placeholder="__('A Link field to DocType')"
				@change="set('options', text($event))"
			/>
		</PanelRow>
		<LinkFiltersRow
			v-if="field.fieldtype === 'Link' && field.options"
			:key="field.options"
			:canvas="canvas"
			:field="field"
			v-bind="mark('link_filters')"
		/>
		<PanelRow :label="__('Required')" :box="false" v-bind="mark('reqd')">
			<div class="flex h-7 items-center px-2">
				<Switch
					size="sm"
					:model-value="Boolean(field.reqd)"
					@update:model-value="set('reqd', $event ? 1 : 0)"
				/>
			</div>
		</PanelRow>
		<PanelRow :label="__('Default')" v-bind="mark('default')">
			<TextInput
				variant="ghost"
				:model-value="field.default ?? ''"
				:placeholder="__('None')"
				@change="set('default', text($event))"
			/>
		</PanelRow>
		<PanelRow
			v-if="fetchable(field)"
			:label="__('Fetch from')"
			:box="false"
			v-bind="mark('fetch_from')"
		>
			<FetchFromRow :canvas="canvas" :field="field" />
		</PanelRow>
		<PanelRow
			v-if="field.fetch_from"
			:label="__('Only when empty')"
			:box="false"
			v-bind="mark('fetch_if_empty')"
		>
			<div class="flex h-7 items-center px-2">
				<Switch
					size="sm"
					:model-value="Boolean(field.fetch_if_empty)"
					data-panel-fetch-if-empty
					@update:model-value="set('fetch_if_empty', $event ? 1 : 0)"
				/>
			</div>
		</PanelRow>
		<PanelRow v-if="field.fieldtype === 'Link' && field.options" label="" :box="false">
			<FetchAddButton :link="field" />
		</PanelRow>
		<PanelRow
			v-if="field.fieldtype !== 'Check'"
			:label="__('Placeholder')"
			v-bind="mark('placeholder')"
		>
			<TextInput
				variant="ghost"
				:model-value="field.placeholder ?? ''"
				:placeholder="__('Add placeholder…')"
				@change="set('placeholder', text($event))"
			/>
		</PanelRow>
		<PanelRow :label="__('Help text')" v-bind="mark('description')">
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
	<FieldRules :canvas="canvas" :field="field" />
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
import FetchAddButton from "./FetchAddButton.vue";
import { fetchable } from "./fetchFrom";
import FetchFromRow from "./FetchFromRow.vue";
import FieldnameRow from "./FieldnameRow.vue";
import {
	removeAction,
	removeQuestion,
	reqdWarning,
	panelMark,
	subtitle,
	takesOff,
	typeChange,
	typeGroups,
	typeNote,
} from "./fieldPanel";
import FieldPropertyGroups from "./FieldPropertyGroups.vue";
import FieldRules from "./FieldRules.vue";
import { typeIcon, typeName } from "./fieldtypes";
import LinkFiltersRow from "./LinkFiltersRow.vue";
import { targetChange } from "./linkFilters";
import PanelHeader from "./PanelHeader.vue";
import PanelRow from "./PanelRow.vue";
import PanelSection from "./PanelSection.vue";
import TableFieldRows from "./TableFieldRows.vue";

const props = defineProps<{ canvas: DesignCanvas; field: RawMetaField }>();

const doctypes = inject<Addresses>("addresses")!.doctypes();
const currentType = computed(() => typeName(props.field.fieldtype, props.field.options));
const note = computed(() => typeNote(props.canvas, props.field));
const errors = computed(() => props.canvas.errorsAt("field", props.field.fieldname));
const warning = computed(() => reqdWarning(props.canvas, props.field.fieldname));
const removal = computed(() => removeAction(props.canvas, props.field));
const anchor = computed(() => props.canvas.customize?.anchor(props.field.fieldname));
const appTitle = computed(() => props.canvas.state.app_title || __("the app"));

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

function setTarget(doctype: string) {
	if (doctype === (props.field.options ?? "")) return;
	void acts.perform("fields.set_field_property", {
		fieldname: props.field.fieldname,
		properties: targetChange(props.field, doctype),
	});
}

function mark(property: string) {
	return panelMark(props.canvas, props.field.fieldname, property);
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
	if (takesOff(props.canvas)) return void acts.perform("canvas.unplace_field", { fieldname });
	if (props.canvas.customize?.hidesOnRemove(fieldname))
		return set("hidden", props.field.hidden ? 0 : 1);
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
