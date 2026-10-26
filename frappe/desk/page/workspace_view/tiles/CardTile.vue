<script setup>
import { Button, ItemListRow, Popover, Tooltip } from "frappe-ui";
import { ChartCard } from "frappe-ui/charts";
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
	<ChartCard>
		<div class="mb-1.5 flex h-[21px] items-center gap-1">
			<span class="truncate text-p-base font-medium text-ink-gray-8">{{
				widget.label
			}}</span>
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
		<ul class="-mx-2 flex flex-col">
			<li v-for="link in widget.links" :key="link.label + link.link_to">
				<Tooltip v-if="is_blocked(link)" :text="blocked_text(link)">
					<ItemListRow disabled>
						<span class="block truncate">{{ link.label }}</span>
					</ItemListRow>
				</Tooltip>
				<Tooltip
					v-else
					:text="link.description ? __(link.description) : undefined"
					:disabled="!link.description"
					:hover-delay="0.6"
				>
					<ItemListRow
						as="button"
						type="button"
						class="text-left hover:bg-surface-gray-2 hover:text-ink-gray-9"
						@click="host.navigate(route_for(link))"
					>
						<span class="block truncate" :class="{ 'font-medium': link.onboard }">
							{{ link.label }}
						</span>
					</ItemListRow>
				</Tooltip>
			</li>
		</ul>
	</ChartCard>
</template>
