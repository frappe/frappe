<template>
	<div class="pfb-inspector pfb-history" @click.stop>
		<div class="pfb-history-head">
			<span class="pfb-history-title">{{ __("Version history") }}</span>
			<button
				class="es-button"
				data-size="xs"
				data-variant="ghost"
				data-icon-button="true"
				:title="__('Save a named version')"
				@click="save_named"
				v-html="frappe.utils.icon('bookmark-plus', 'sm')"
			></button>
			<button
				class="es-button"
				data-size="xs"
				data-variant="ghost"
				data-icon-button="true"
				:title="__('Close')"
				@click="$emit('close')"
				v-html="frappe.utils.icon('x', 'sm')"
			></button>
		</div>
		<div class="pfb-history-list">
			<div class="pfb-history-row pfb-history-row--current">
				<span class="pfb-history-dot" data-kind="current"></span>
				<div class="pfb-history-text">
					<div class="pfb-history-name">{{ __("Current version") }}</div>
					<div class="pfb-history-meta">
						{{
							has_draft
								? __("Working draft · not applied yet")
								: __("Same as what prints")
						}}
					</div>
				</div>
			</div>
			<div class="pfb-history-row">
				<span class="pfb-history-dot" data-kind="published"></span>
				<div class="pfb-history-text">
					<div class="pfb-history-name">{{ __("Published version") }}</div>
					<div class="pfb-history-meta">
						{{ __("What prints now") }} · {{ when(print_format.modified) }}
					</div>
				</div>
				<button
					v-if="has_draft"
					class="es-button pfb-history-restore"
					data-size="xs"
					data-variant="ghost"
					data-icon-button="true"
					:title="__('Discard the draft and go back to this')"
					@click="discard"
					v-html="frappe.utils.icon('rotate-ccw', 'sm')"
				></button>
				<span v-html="frappe.avatar(print_format.modified_by, 'avatar-small')"></span>
			</div>
			<div v-if="versions.length" class="pfb-history-label">{{ __("Saved versions") }}</div>
			<div v-for="v in versions" :key="v.name" class="pfb-history-row">
				<span
					class="pfb-history-dot"
					:data-kind="v.type === 'Manual' ? 'named' : 'saved'"
				></span>
				<div class="pfb-history-text">
					<div class="pfb-history-name">{{ v.label || __("Saved") }}</div>
					<div class="pfb-history-meta">
						<template v-if="v.type !== 'Manual'">{{ __("Save & Apply") }} · </template>
						{{ when(v.creation) }}
					</div>
				</div>
				<button
					class="es-button pfb-history-restore"
					data-size="xs"
					data-variant="ghost"
					data-icon-button="true"
					:title="__('Restore this version as your draft')"
					@click="restore(v)"
					v-html="frappe.utils.icon('rotate-ccw', 'sm')"
				></button>
				<span v-html="frappe.avatar(v.owner, 'avatar-small')"></span>
			</div>
		</div>
	</div>
</template>

<script setup>
import { inject, onMounted } from "vue";

defineEmits(["close"]);
const store = inject("$store");
const { print_format, has_draft, versions } = store;

function when(value) {
	return frappe.datetime.prettyDate(value);
}

function save_named() {
	frappe.prompt(
		{ fieldname: "label", fieldtype: "Data", label: __("Version name"), reqd: 1 },
		({ label }) => store.save_version(label),
		__("Save version"),
		__("Save")
	);
}

function restore(v) {
	frappe.confirm(
		__(
			"Replace your current draft with {0}? Nothing prints differently until you Save & Apply.",
			[frappe.bold(v.label || when(v.creation))]
		),
		() => store.restore_version(v.name)
	);
}

function discard() {
	frappe.confirm(
		__("Discard your unapplied changes and go back to what this format prints?"),
		() => store.discard_draft()
	);
}

onMounted(() => store.load_versions());
</script>

<style scoped>
.pfb-history-head {
	display: flex;
	align-items: center;
	gap: 4px;
	padding: 10px 10px 10px 14px;
	border-bottom: 1px solid var(--border-color);
}
.pfb-history-title {
	flex: 1;
	font-weight: var(--weight-semibold);
	font-size: var(--text-base);
}
.pfb-history-list {
	padding: 8px;
	overflow-y: auto;
}
.pfb-history-row {
	display: flex;
	align-items: flex-start;
	gap: 10px;
	padding: 8px 10px;
	border-radius: var(--radius);
}
.pfb-history-row:hover {
	background: var(--surface-gray-1);
}
.pfb-history-row--current {
	background: var(--surface-gray-2);
}
.pfb-history-dot {
	width: 8px;
	height: 8px;
	margin-top: 6px;
	border-radius: 50%;
	flex-shrink: 0;
	background: var(--gray-400);
}
.pfb-history-dot[data-kind="published"] {
	background: var(--green-500);
}
.pfb-history-dot[data-kind="named"] {
	background: var(--blue-500);
}
.pfb-history-text {
	flex: 1;
	min-width: 0;
}
.pfb-history-name {
	font-size: var(--text-base);
	color: var(--text-color);
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}
.pfb-history-meta {
	font-size: var(--text-sm);
	color: var(--text-muted);
}
.pfb-history-label {
	padding: 10px 10px 4px;
	font-size: var(--text-xs);
	color: var(--text-muted);
}
.pfb-history-restore {
	visibility: hidden;
}
.pfb-history-row:hover .pfb-history-restore {
	visibility: visible;
}
</style>
