<!-- "Edit series": every Naming Series option at once, with its next name and the default. It edits
     a copy; Done hands the list back, Cancel drops it. -->
<template>
	<Dialog
		v-model:open="open"
		:title="__('Naming Series')"
		size="2xl"
		@after-leave="emit('closed')"
	>
		<div ref="body" class="flex flex-col" data-series-dialog>
			<p class="mb-4 text-p-base text-ink-gray-6">
				{{
					__("Each series counts on its own. The person who creates a {0} picks one.", [
						view.doctype,
					])
				}}
			</p>
			<div class="flex h-6 items-center gap-3 text-sm text-ink-gray-6">
				<span class="w-[260px] shrink-0">{{ __("Series") }}</span>
				<span class="flex-1">{{ __("Next name") }}</span>
				<span class="w-14 shrink-0 text-center">{{ __("Default") }}</span>
				<span class="w-7 shrink-0" />
			</div>
			<div
				v-for="(row, at) in rows"
				:key="row.id"
				class="flex h-9 items-center gap-3"
				data-series-row
			>
				<TextInput
					v-model="row.text"
					class="w-[260px] shrink-0 [&_input]:font-mono [&_input]:text-sm"
					:placeholder="example"
					:aria-label="__('Series')"
					:autofocus="at === 0"
					@focus.once="at === 0 && caretToEnd($event)"
					autocomplete="off"
				/>
				<Tooltip :text="fullName(row.text)">
					<NamePreview
						class="block min-w-0 flex-1 truncate whitespace-nowrap pt-0.5"
						:parts="next(row.text)"
					/>
				</Tooltip>
				<!-- One group per row keeps Tab in visual order: input, default, remove. -->
				<RadioGroup v-model="chosen" class="flex w-14 shrink-0 justify-center">
					<!-- Radio's label gutter would push the circle off centre. -->
					<Radio
						:value="row.id"
						class="!-m-[7px] !items-center !gap-0 !p-[7px] hover:!bg-surface-gray-3 focus-visible:!ring-2 focus-visible:!ring-outline-gray-5 [&>span:first-child]:!mt-0 [&[data-state=unchecked]>span:first-child]:!border-outline-gray-5"
						:aria-label="
							__('Make {0} the default', [row.text.trim() || __('new series')])
						"
					/>
				</RadioGroup>
				<Tooltip :text="__('Remove series')">
					<Button
						variant="ghost"
						icon="lucide-x"
						class="focus-visible:!outline-none focus-visible:!ring-2 focus-visible:!ring-outline-gray-5"
						:aria-label="__('Remove series')"
						:disabled="rows.length < 2"
						@click="remove(at)"
					/>
				</Tooltip>
			</div>

			<Button
				size="sm"
				variant="subtle"
				icon-left="lucide-plus"
				:label="__('Add a series')"
				class="mt-1 w-fit"
				data-series-add
				@click="add"
			/>
			<p class="mt-4 text-p-sm text-ink-gray-6">
				{{ __("A dot ends the text part, and # marks the counter's digits:") }}
				<span class="whitespace-nowrap font-mono">ACC-SINV-.YYYY.-.#####</span>
				{{ __("gives") }}
				<span class="whitespace-nowrap font-mono">ACC-SINV-2026-00001</span>.
			</p>
		</div>
		<template #actions>
			<div class="flex justify-end gap-2">
				<Button :label="__('Cancel')" @click="open = false" />
				<Button
					variant="solid"
					:label="__('Done')"
					:disabled="!list.length"
					@click="done"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, inject, nextTick, reactive, ref } from "vue";
import { Button, Dialog, Radio, RadioGroup, TextInput, Tooltip } from "frappe-ui";
import { __ } from "@/i18n";
import NamePreview from "./NamePreview.vue";
import { nextName } from "./namingPattern";
import { useSeriesCounters } from "./seriesCounters";
import { SettingsViewKey } from "./settingsView";

const props = defineProps<{
	series: string[];
	preferred: string;
	counters: Record<string, number>;
}>();
const emit = defineEmits<{ done: [list: string[], preferred: string]; closed: [] }>();
const open = defineModel<boolean>("open", { default: false });
const view = inject(SettingsViewKey)!;
const body = ref<HTMLElement>();

let ids = 0;
const row = (text: string) => reactive({ id: ids++, text });
const rows = ref(props.series.map(row));
const chosen = ref(rows.value[Math.max(0, props.series.indexOf(props.preferred))]?.id);

const example = __("e.g. ST-.YYYY.-.#####");
const list = computed(() => [
	...new Set(rows.value.map((one) => one.text.trim()).filter(Boolean)),
]);

// The rows are drafts: a prefix typed here is counted from the site, not from the saved options.
const drafted = useSeriesCounters(view, () => rows.value.map((one) => one.text.trim()));
const counted = computed(() => ({ ...props.counters, ...drafted.value }));

function next(text: string) {
	const series = text.trim();
	if (!series) return [];
	return nextName(series, counted.value, view.label.bind(view), new Date());
}

function fullName(text: string) {
	return next(text)
		.map((part) => part.text)
		.join("");
}

// The dialog's autofocus selects the whole first series; the first keystroke would replace it.
function caretToEnd(event: FocusEvent) {
	const input = event.target as HTMLInputElement;
	setTimeout(() => input.setSelectionRange(input.value.length, input.value.length));
}

async function add() {
	rows.value.push(row(""));
	await nextTick();
	const inputs = body.value?.querySelectorAll<HTMLInputElement>("[data-series-row] input") ?? [];
	inputs[inputs.length - 1]?.focus();
}

function remove(at: number) {
	const [gone] = rows.value.splice(at, 1);
	if (gone.id === chosen.value) chosen.value = rows.value[0].id;
}

function done() {
	const favourite = rows.value.find((one) => one.id === chosen.value)?.text.trim();
	const first = list.value.includes(favourite ?? "") ? favourite! : list.value[0];
	emit("done", [first, ...list.value.filter((one) => one !== first)], first);
	open.value = false;
}
</script>
