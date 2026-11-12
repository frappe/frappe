<!-- The bulk Print dialog: the print format, letterhead and page size; the PDF is a background run. -->
<template>
	<Dialog v-model="open" :title="title" size="sm" :actions="actions">
		<template #default>
			<div class="flex flex-col gap-4">
				<Select
					v-model="printFormat"
					:label="__('Print Format')"
					:options="formatOptions"
				/>
				<Select
					v-model="letterhead"
					:label="__('Letter Head')"
					:options="letterheadOptions"
				/>
				<Select v-model="pageSize" :label="__('Page Size')" :options="sizeOptions" />
			</div>
			<p v-if="failure" role="alert" class="mt-3 whitespace-pre-line text-sm text-ink-red-4">
				{{ failure }}
			</p>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { listDocuments, type BulkPrintBody } from "@framework/ui/api";
import { Dialog, Select, toast } from "frappe-ui";
import { computed, onMounted, ref, watch } from "vue";
import { __, __n } from "@/i18n";
import { DEFAULT, NO_LETTERHEAD, PAGE_SIZES, printBody, printableFormats } from "./printOptions";
import { startBulkPrint } from "./printRun";

const props = defineProps<{
	doctype: string;
	count: number;
	all?: boolean;
	approx?: boolean;
	scope: BulkPrintBody;
}>();
const open = defineModel<boolean>({ default: false });

const printFormat = ref(DEFAULT);
const letterhead = ref(DEFAULT);
const pageSize = ref(DEFAULT);
const formats = ref<string[]>([]);
const letterheads = ref<string[]>([]);
const starting = ref(false);
const failure = ref("");

const title = computed(() =>
	props.all
		? __("Print all {0} matching records", [
				props.count.toLocaleString() + (props.approx ? "+" : ""),
		  ])
		: __n("Print {0} selected record", "Print {0} selected records", props.count, [
				props.count,
		  ])
);

const defaultOption = { label: __("Default"), value: DEFAULT };
const formatOptions = computed(() => [defaultOption, ...formats.value.map(named)]);
const letterheadOptions = computed(() => [
	defaultOption,
	{ label: __("No Letterhead"), value: NO_LETTERHEAD },
	...letterheads.value.map(named),
]);
const sizeOptions = [defaultOption, ...PAGE_SIZES.map(named)];

const actions = computed(() => [
	{ label: __("Print"), variant: "solid" as const, loading: starting.value, onClick: print },
]);

watch(open, (isOpen) => isOpen && (failure.value = ""));

onMounted(async () => {
	const [printFormats, heads] = await Promise.allSettled([
		listDocuments<Record<string, unknown>>("Print Format", {
			fields: ["name", "print_format_type", "print_format_for", "raw_printing"],
			filters: { doc_type: props.doctype, disabled: 0 },
			order_by: "name asc",
			limit: 500,
		}),
		listDocuments<{ name: string }>("Letter Head", {
			fields: ["name"],
			filters: { disabled: 0 },
			order_by: "name asc",
			limit: 500,
		}),
	]);
	if (printFormats.status === "fulfilled")
		formats.value = printableFormats(printFormats.value.data);
	if (heads.status === "fulfilled") letterheads.value = heads.value.data.map(({ name }) => name);
});

async function print() {
	starting.value = true;
	failure.value = "";
	try {
		await startBulkPrint(
			props.doctype,
			printBody(props.scope, {
				printFormat: printFormat.value,
				letterhead: letterhead.value,
				pageSize: pageSize.value,
			})
		);
		toast.info(__("Printing in the background"));
		open.value = false;
	} catch (error) {
		failure.value = error instanceof Error ? error.message : String(error);
	} finally {
		starting.value = false;
	}
}

function named(name: string) {
	return { label: name, value: name };
}
</script>
