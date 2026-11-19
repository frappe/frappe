import { __ } from "frappe/i18n";

const RECORDER = "frappe.recorder";

const START_FIELDS = [
	{ fieldname: "record_requests", fieldtype: "Check", label: __("Record Web Requests") },
	{
		fieldname: "request_filter",
		fieldtype: "Data",
		label: __("Request path filter"),
		depends_on: "record_requests",
		description: __(
			"Records only the paths that start with it, e.g. /api/method/erpnext. Leave it empty to record every request."
		),
	},
	{ fieldname: "record_jobs", fieldtype: "Check", label: __("Record Background Jobs") },
	{
		fieldname: "jobs_filter",
		fieldtype: "Data",
		label: __("Background Jobs filter"),
		depends_on: "record_jobs",
		description: __(
			"Records only the jobs that match it, e.g. email_queue.pull. Leave it empty to record every job."
		),
	},
	{ fieldname: "record_sql", fieldtype: "Check", label: __("Record SQL queries") },
	{ fieldname: "explain", fieldtype: "Check", label: __("Generate EXPLAIN for SQL queries") },
	{
		fieldname: "capture_stack",
		fieldtype: "Check",
		label: __("Capture callstack of SQL queries"),
	},
	{
		fieldname: "capture_doc_events",
		fieldtype: "Check",
		label: __("Capture document lifecycle timeline"),
	},
	{
		fieldname: "profile",
		fieldtype: "Check",
		label: __("Run cProfile"),
		description: __(
			"cProfile adds a lot of overhead. For best results, do not capture the callstack with it."
		),
	},
];
const START_DEFAULTS = {
	record_requests: 1,
	request_filter: "/",
	record_jobs: 1,
	jobs_filter: "",
	record_sql: 1,
	explain: 1,
	capture_stack: 1,
	capture_doc_events: 1,
	profile: 0,
};

// Desk v1 showed Start or Stop from frappe.recorder.status, a read a cold list load must not make.
export default {
	onRefresh(page) {
		const isAdministrator = (page) => page.roles.includes("Administrator");
		page.header.add({
			name: "start_recording",
			label: __("Start"),
			icon: "lucide-circle-play",
			display: "button",
			when: isAdministrator,
			run: start,
		});
		page.header.add({
			name: "stop_recording",
			label: __("Stop"),
			icon: "lucide-circle-stop",
			display: "button",
			when: isAdministrator,
			run: stop,
		});
		page.header.add({
			name: "clear_recordings",
			label: __("Clear"),
			when: isAdministrator,
			run: clear,
		});
		page.header.add({
			name: "export_recordings",
			label: __("Export"),
			when: isAdministrator,
			run: exportRecordings,
		});
	},
};

async function start(page) {
	const values = await page.dialog.form({
		title: __("Configure Recorder"),
		fields: START_FIELDS,
		defaults: START_DEFAULTS,
		submitLabel: __("Start Recording"),
	});
	if (!values) return;
	await page.call(`${RECORDER}.start`, values);
	page.toast.success(__("Recorder started"));
}

async function stop(page) {
	await page.call(`${RECORDER}.stop`);
	page.toast.success(__("Recorder stopped"));
	page.reload();
}

async function clear(page) {
	await page.call(`${RECORDER}.delete`);
	page.reload();
}

async function exportRecordings(page) {
	const data = await page.call(`${RECORDER}.export_data`);
	if (!data?.length) return page.toast.info(__("Nothing recorded to export"));
	const link = document.createElement("a");
	link.href = URL.createObjectURL(
		new Blob([JSON.stringify(data)], { type: "application/json" })
	);
	link.download = `${data[0].uuid}..${data[data.length - 1].uuid}.json`;
	link.click();
	URL.revokeObjectURL(link.href);
}
