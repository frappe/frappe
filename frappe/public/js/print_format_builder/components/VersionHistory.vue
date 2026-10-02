<template>
	<div class="pfb-history-list">
		<div
			v-if="has_draft"
			class="pfb-history-row pfb-history-row--link"
			:class="{ 'pfb-history-row--current': !viewing_version }"
			@click="store.versions.exit()"
		>
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
		<div
			class="pfb-history-row pfb-history-row--link"
			:class="{
				'pfb-history-row--current':
					viewing_version?.published || (!has_draft && !viewing_version),
			}"
			@click="
				has_draft
					? view({
							published: true,
							label: __('Published version'),
							when: when(print_format.modified),
					  })
					: store.versions.exit()
			"
		>
			<span class="pfb-history-dot" data-kind="published"></span>
			<div class="pfb-history-text">
				<div class="pfb-history-name">{{ __("Published version") }}</div>
				<div class="pfb-history-meta">
					{{ has_draft ? __("What prints now") : __("Current version") }} ·
					{{ when(print_format.modified) }}
				</div>
			</div>
			<button
				v-if="has_draft"
				class="es-button pfb-history-action"
				data-size="xs"
				data-variant="ghost"
				data-icon-button="true"
				:title="__('Discard the draft and go back to this')"
				@click.stop="discard"
				v-html="frappe.utils.icon('rotate-ccw', 'sm')"
			></button>
			<span v-html="frappe.avatar(print_format.modified_by, 'avatar-xs')"></span>
		</div>
		<div v-if="versions.length" class="pfb-history-label">{{ __("Saved versions") }}</div>
		<div
			v-for="v in versions"
			:key="v.name"
			class="pfb-history-row pfb-history-row--link"
			:class="{ 'pfb-history-row--current': viewing_version?.name === v.name }"
			@click="view({ ...v, label: v.label || __('Saved'), when: when(v.creation) })"
		>
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
				class="es-button pfb-history-action"
				data-size="xs"
				data-variant="ghost"
				data-icon-button="true"
				:title="__('Restore this version as your draft')"
				@click.stop="restore(v)"
				v-html="frappe.utils.icon('rotate-ccw', 'sm')"
			></button>
			<button
				class="es-button pfb-history-action"
				data-size="xs"
				data-variant="ghost"
				data-theme="red"
				data-icon-button="true"
				:title="__('Delete this version')"
				@click.stop="remove(v)"
				v-html="frappe.utils.icon('trash', 'sm')"
			></button>
			<span v-html="frappe.avatar(v.owner, 'avatar-xs')"></span>
		</div>
	</div>
</template>

<script setup>
import { inject, onMounted } from "vue";

const store = inject("$store");
const { print_format } = store;
const { has_draft } = store.draft;
const { list: versions, viewing: viewing_version } = store.versions;

function when(value) {
	return frappe.datetime.prettyDate(value);
}

function view(version) {
	store.versions.view(version);
}

function restore(v) {
	frappe.confirm(
		__(
			"Replace your current draft with {0}? Nothing prints differently until you Save & Apply.",
			[frappe.utils.bold(v.label || when(v.creation))]
		),
		() => store.versions.restore(v.name)
	);
}

function remove(v) {
	frappe.confirm(
		__("Delete the version {0}? This cannot be undone.", [
			frappe.utils.bold(v.label || when(v.creation)),
		]),
		() => store.versions.remove(v.name)
	);
}

function discard() {
	frappe.confirm(
		__("Discard your unapplied changes and go back to what this format prints?"),
		() => store.draft.discard()
	);
}

onMounted(() => store.versions.load());
</script>

<style scoped>
.pfb-history-list {
	padding: 8px;
	overflow-y: auto;
}
.pfb-history-row {
	display: flex;
	align-items: center;
	gap: 8px;
	padding: 6px 10px;
	border-radius: var(--radius);
}
.pfb-history-row--link {
	cursor: pointer;
}
.pfb-history-row--link:hover {
	background: var(--surface-gray-1);
}
.pfb-history-row--current {
	background: var(--surface-gray-2);
}
.pfb-history-dot {
	width: 6px;
	height: 6px;
	border-radius: 50%;
	flex-shrink: 0;
	background: var(--surface-gray-5);
}
.pfb-history-dot[data-kind="published"] {
	background: var(--surface-green-5);
}
.pfb-history-dot[data-kind="named"] {
	background: var(--surface-blue-5);
}
.pfb-history-text {
	flex: 1;
	min-width: 0;
}
.pfb-history-name {
	font-size: var(--text-sm);
	font-weight: var(--weight-medium);
	color: var(--text-color);
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}
.pfb-history-meta {
	font-size: var(--text-xs);
	color: var(--text-muted);
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}
.pfb-history-label {
	padding: 10px 10px 2px;
	font-size: var(--text-xs);
	color: var(--text-muted);
}
.pfb-history-row :deep(.avatar-xs) {
	width: 24px;
	height: 24px;
	font-size: var(--text-xs);
}
.pfb-history-action {
	visibility: hidden;
}
.pfb-history-row:hover .pfb-history-action {
	visibility: visible;
}
</style>
