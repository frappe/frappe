// Export on a bulk scope: the Data Exporter takes `export_filters` and no `or_filters`.
import type { BulkSelection } from "@framework/ui/api";

/** The filters `download_template` exports; null when the scope has `or_filters`, which it cannot take. */
export function exportFilters(selection: BulkSelection): Record<string, unknown> | null {
	if (selection.names) return { name: ["in", selection.names] };
	const { or_filters: orFilters } = selection;
	const hasOr = Array.isArray(orFilters) ? orFilters.length > 0 : !!orFilters && Object.keys(orFilters).length > 0;
	return hasOr ? null : ((selection.filters as Record<string, unknown> | undefined) ?? {});
}
