frappe.pages['background_jobs'].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Background Jobs'),
		single_column: true
	});

	$(frappe.render_template('background_jobs_outer')).appendTo(page.body);
	page.content = $(page.body).find('.table-area');

	frappe.pages.background_jobs.page = page;
}

frappe.pages['background_jobs'].on_page_show = function(wrapper) {
	frappe.pages.background_jobs.refresh_jobs();
	frappe.call({
		method: 'frappe.core.page.background_jobs.background_jobs.get_scheduler_status',
		callback: function(r) {
			frappe.pages.background_jobs.page.set_indicator(...r.message);
		}
	});
}

frappe.pages.background_jobs.refresh_jobs = async function refresh_jobs() {
	const page = frappe.pages.background_jobs.page;
	const info = (await frappe.call('frappe.core.page.background_jobs.background_jobs.get_info')).message;
	push_to_dataset(info.pending_jobs);
	frappe.background_jobs_timeout = setTimeout(frappe.pages.background_jobs.refresh_jobs, 2000);
}

function push_to_dataset(pending_jobs) {
	const dataset_size = 11;
	let background_jobs_dataset = window.background_jobs_dataset;
	if (!window.background_jobs_dataset) {
		background_jobs_dataset = window.background_jobs_dataset = {};
	}
	for (const queue in pending_jobs) {
		const new_data = pending_jobs[queue];
		const dataset = background_jobs_dataset[queue];
		if (!dataset) {
			background_jobs_dataset[queue] = {
				success: Array(dataset_size).fill(0),
				success_diff: Array(dataset_size).fill(0),
				failed: Array(dataset_size).fill(0),
				failed_diff: Array(dataset_size).fill(0),
			};
			continue;
		}
		dataset.success_diff.push(new_data[2] - (dataset.success.slice(-1)[0] || new_data[2]));
		dataset.success.push(new_data[2]);
		dataset.failed_diff.push(new_data[3] - (dataset.failed.slice(-1)[0] || new_data[3]));
		dataset.failed.push(new_data[3]);
		const length = dataset.success.length;
		for (const arr of Object.values(dataset)) {
			arr.splice(0, dataset_size < arr.length ? 1 : 0);
		}
	}
	// console.log(JSON.stringify(background_jobs_dataset, null, 2));
	render_pending_jobs(pending_jobs, background_jobs_dataset, dataset_size);
}

function render_pending_jobs(pending_jobs, background_jobs_dataset, dataset_size) {
	const wrapper = $('.pending-jobs>tbody');
	// wrapper.html('');
	Object.keys(pending_jobs).sort().forEach(key => {
		const tr_wrapper = $('#queue-row-' + key);
		if (!tr_wrapper.length) {
			init_row(wrapper, key, pending_jobs[key], background_jobs_dataset[key], dataset_size);
		} else {
			update_row(tr_wrapper, key, pending_jobs[key], background_jobs_dataset[key], dataset_size);
		}
	});
}

function init_row(wrapper, key, job_meta, dataset, dataset_size) {
	const [pending, total, success, failed] = job_meta;
	wrapper.append(`
		<tr id="queue-row-${key}" >
			<td> ${key} </td>
			<td> ${pending} </td>
			<td><div id="queue-chart-${key}"></div></td>
			<td> ${total} </td>
			<td> ${success} </td>
			<td> ${failed} </td>
		<tr>
	`);
	const charts = frappe.pages.background_jobs.charts = (frappe.pages.background_jobs.charts || {});
	const labels = Array(dataset_size);
	for (let i=0; i<dataset_size; i++) {
		labels[i] = i * 2;
	}
	charts[key] = new frappe.Chart(`#queue-chart-${key}`, {
		data: {
			labels,
			datasets: [{
				name: "Success",
				chartType: "line",
				values: dataset.success_diff,
			},
			{
				name: "Failed",
				chartType: "line",
				values: dataset.failed_diff,
			}],
		},
		type: "line",
		height: 200,
		colors: ["green", "red"],
		axisOptions: {
			xAxisMode: "tick",
			xIsSeries: true,
		},
		lineOptions: {
			hideDots: 1,
			spline: 1,
		},
		tooltipOptions: {
			formatTooltipX: d => (d + "").toUpperCase(),
			formatTooltipY: d => d + " pts",
		}
	});
}

function update_row(tr_wrapper, key, job_meta, dataset) {
	const [pending, total, success, failed] = job_meta;
	const [_, pending_wr, __, total_wr, success_wr, failed_wr] = tr_wrapper.find('td');
	pending_wr.innerText = pending;
	total_wr.innerText = total;
	success_wr.innerText = success;
	failed_wr.innerText = failed;
	frappe.pages.background_jobs.charts[key].updateDatasets([
		dataset.success_diff,
		dataset.failed_diff,
	]);
}