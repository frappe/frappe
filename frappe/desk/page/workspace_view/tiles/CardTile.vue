<script setup>
import { Button, Popover, Tooltip } from "frappe-ui";
import { useHost } from "@framework/ui/island";

defineProps({
	widget: { type: Object, required: true },
});

const frappe = window.frappe;
const __ = window.__;
const host = useHost();

function route_for(link) {
	const opts = {
		name: link.link_to,
		type: link.link_type,
		is_query_report: link.is_query_report,
		report_ref_doctype: link.report_ref_doctype,
	};
	if (link.link_type.toLowerCase() === "report" && !link.is_query_report) {
		opts.doctype = link.dependencies;
	}
	return frappe.utils.generate_route(opts);
}

function is_blocked(link) {
	return link.dependencies && link.incomplete_dependencies;
}

function blocked_text(link) {
	return __("You need to create these first:") + " " + link.incomplete_dependencies.join(", ");
}
</script>

<template>
	<div class="rounded-6 border border-outline-gray-1 bg-surface-base p-4">
		<div class="mb-2 flex items-center gap-1">
			<span class="truncate text-base font-medium text-ink-gray-8">{{ widget.label }}</span>
			<Popover v-if="widget.description" side="top">
				<template #trigger>
					<Button
						size="sm"
						variant="ghost"
						icon="lucide-circle-help"
						:label="__('About {0}', [widget.label])"
					/>
				</template>
				<div class="max-w-64 p-2 text-sm text-ink-gray-7">
					{{ __(widget.description) }}
				</div>
			</Popover>
		</div>
		<ul class="flex flex-col">
			<li v-for="link in widget.links" :key="link.label + link.link_to">
				<Tooltip v-if="is_blocked(link)" :text="blocked_text(link)">
					<span class="block truncate py-1 text-base text-ink-gray-4">{{
						link.label
					}}</span>
				</Tooltip>
				<Tooltip
					v-else-if="link.description"
					:text="__(link.description)"
					:hover-delay="0.6"
				>
					<button
						type="button"
						class="block w-full truncate rounded py-1 text-left text-base text-ink-gray-7 hover:text-ink-gray-9"
						:class="{ 'font-medium': link.onboard }"
						@click="host.navigate(route_for(link))"
					>
						{{ link.label }}
					</button>
				</Tooltip>
				<button
					v-else
					type="button"
					class="block w-full truncate rounded py-1 text-left text-base text-ink-gray-7 hover:text-ink-gray-9"
					:class="{ 'font-medium': link.onboard }"
					@click="host.navigate(route_for(link))"
				>
					{{ link.label }}
				</button>
			</li>
		</ul>
	</div>
</template>
