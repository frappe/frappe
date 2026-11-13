<!-- The canvas, read-only for now: the Details layout's tabs, sections, columns and field labels.
     #47272 makes it editable; the record page's own FormLayout draws the Preview tab instead. -->
<template>
	<div class="mx-auto w-full max-w-3xl py-6" data-editor-canvas>
		<h1 class="text-xl font-semibold text-ink-gray-9">{{ state.doctype }}</h1>
		<p class="mt-1 text-p-sm text-ink-gray-5" data-editor-meta>{{ metaLine }}</p>
		<p v-if="state.site_custom_fields" class="mt-1 text-p-sm text-ink-gray-5">
			{{
				__("{0} fields added on this site, edit them in Customize.", [
					state.site_custom_fields,
				])
			}}
		</p>

		<div v-if="tabs.length > 1" class="mt-6 flex gap-5 border-b" role="tablist">
			<button
				v-for="(one, index) in tabs"
				:key="one.name ?? index"
				type="button"
				role="tab"
				class="-mb-px border-b-2 pb-2 text-base"
				:class="
					index === open
						? 'border-outline-gray-5 text-ink-gray-9'
						: 'border-transparent text-ink-gray-5'
				"
				@click="open = index"
			>
				{{ one.label || __("Details") }}
			</button>
		</div>

		<div class="mt-4 flex flex-col gap-3">
			<section
				v-for="(section, index) in tabs[open]?.sections ?? []"
				:key="section.name ?? index"
				class="rounded-7 border border-outline-gray-1 p-4"
				data-canvas-section
			>
				<h2 v-if="section.label" class="mb-3 text-base font-medium text-ink-gray-8">
					{{ section.label }}
				</h2>
				<div
					class="grid gap-4"
					:style="{
						gridTemplateColumns: `repeat(${
							section.columns.length || 1
						}, minmax(0, 1fr))`,
					}"
				>
					<div
						v-for="(column, at) in section.columns"
						:key="column.name ?? at"
						class="flex flex-col gap-2"
					>
						<div
							v-for="field in column.fields"
							:key="fieldnameOf(field)"
							class="flex h-8 items-center justify-between rounded-4 bg-surface-gray-2 px-2.5 text-base text-ink-gray-7"
							data-canvas-field
						>
							<span class="truncate">{{ labelOf(field) }}</span>
							<span class="shrink-0 text-p-xs text-ink-gray-5">{{
								typeOf(field)
							}}</span>
						</div>
					</div>
				</div>
			</section>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { __ } from "@/i18n";
import type { InlineField, LayoutTree } from "@/recordPage/formLayoutSource/types";
import type { EditorState } from "./editorSource";

const props = defineProps<{ state: EditorState; layout: LayoutTree; metaLine: string }>();

const open = ref(0);
const tabs = computed(() => props.layout ?? []);
const fields = computed(
	() => new Map(props.state.definition.fields.map((field) => [field.fieldname, field]))
);

function fieldnameOf(field: string | InlineField) {
	return typeof field === "string" ? field : field.fieldname;
}

function labelOf(field: string | InlineField) {
	const name = fieldnameOf(field);
	return fields.value.get(name)?.label || (typeof field === "string" ? "" : field.label) || name;
}

function typeOf(field: string | InlineField) {
	return fields.value.get(fieldnameOf(field))?.fieldtype ?? "";
}
</script>
