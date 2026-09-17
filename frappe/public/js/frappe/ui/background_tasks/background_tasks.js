frappe.ui.BackgroundTasks = class BackgroundTasks {
	constructor() {
		this.db_tasks = [];
		this.has_fetched = false;
		this.make();
	}

	make() {
		this.panel = new frappe.ui.SidebarPanel({
			name: "background-tasks",
			title: __("Background Tasks"),
			trigger_selector: ".sidebar-background-tasks",
			on_open: () => this.on_open(),
		});
		this.body = this.panel.$body;

		this.setup_events();
		this.update_tasks();
	}

	/** Whether the panel is on screen. Realtime updates only touch the DOM when it is. */
	get is_open() {
		return this.panel.is_open;
	}

	// The list is fetched once and then kept current by realtime, so opening only has to
	// catch the DOM up with whatever arrived while the panel was hidden.
	on_open() {
		if (this.has_fetched) {
			this.render_tasks(this.db_tasks);
		} else {
			this.update_tasks();
		}
	}

	// A trigger lives in the sidebar and another in the dock's rail, and the rail is built
	// after this view on some navigations. Re-queried each call so both are covered, the same
	// way the unread count reaches every bell.
	toggle_button_visibility() {
		$(".sidebar-background-tasks").toggleClass("hidden", !this.db_tasks?.length);
	}

	setup_events() {
		this.panel.$panel.on("click", ".bg-task-item", (e) => {
			let name = $(e.currentTarget).data("name");
			if (name) {
				frappe.set_route("background-task", name);
			}
			this.panel.hide();
		});

		this.panel.$panel.on("click", ".bg-task-footer", () => {
			frappe.set_route("background-task");
			this.panel.hide();
		});

		this.panel.$panel.on("click", ".btn-cancel-task", (e) => {
			e.preventDefault();
			e.stopPropagation();
			let task_id = $(e.currentTarget).data("task-id");
			frappe.call({
				method: "frappe.core.doctype.background_task.background_task.stop_task",
				args: { task_id: task_id },
			});
		});

		this.panel.$panel.on("click", ".btn-retry-task", (e) => {
			e.preventDefault();
			e.stopPropagation();
			let task_id = $(e.currentTarget).data("task-id");
			frappe.call({
				method: "frappe.core.doctype.background_task.background_task.retry_task",
				args: { task_id: task_id },
			});
		});

		// Listen for realtime updates to refresh list and show alerts
		frappe.realtime.on("task_update", (data) => {
			let task = this.db_tasks.find((t) => t.task_id === data.task_id);
			let status_changed = false;

			if (task) {
				if (data.progress !== undefined) {
					task.progress = data.progress;
				}
				if (data.stage !== undefined) {
					task.stage = data.stage;
				}
				if (data.status && data.status !== task.status) {
					task.status = data.status;
					status_changed = true;
				}

				if (this.is_open) {
					if (status_changed) {
						this.render_tasks(this.db_tasks);
					} else {
						let $task = this.body.find(`[data-task-id="${data.task_id}"]`);
						if (data.progress !== undefined) {
							$task
								.find(".progress-bar")
								.css("width", `${data.progress}%`)
								.attr("aria-valuenow", data.progress);
						}
						if (data.stage !== undefined) {
							$task.find(".bg-task-stage").text(data.stage);
						}
					}
				}
			} else if (data.status && this.has_fetched) {
				// New task
				frappe.db
					.get_list("Background Task", {
						filters: { task_id: data.task_id },
						fields: [
							"name",
							"task_id",
							"task_name",
							"status",
							"stage",
							"progress",
							"show_progress_bar",
							"allow_user_cancellation",
							"allow_user_retry",
							"creation",
						],
						limit: 1,
					})
					.then((tasks) => {
						if (tasks && tasks.length) {
							this.db_tasks.unshift(tasks[0]);
							if (this.db_tasks.length > 15) this.db_tasks.pop();
							this.toggle_button_visibility();
							if (this.is_open) {
								this.render_tasks(this.db_tasks);
							}
						}
					});
			}

			if (data.status) {
				const title = frappe.utils.escape_html(data.task_name || __("Background Task"));
				const alerts = {
					Queued: { message: __("{0} queued", [title]), indicator: "blue" },
					Running: { message: __("{0} started", [title]), indicator: "blue" },
					Completed: { message: __("{0} completed", [title]), indicator: "green" },
					Failed: { message: __("{0} failed", [title]), indicator: "red" },
					Cancelled: { message: __("{0} cancelled", [title]), indicator: "orange" },
				};

				if (alerts[data.status]) {
					frappe.show_alert(alerts[data.status]);
				}
			}
		});
	}

	update_tasks() {
		frappe
			.call({
				method: "frappe.core.doctype.background_task.background_task.get_recent_tasks",
				args: { limit: 15 },
			})
			.then((r) => {
				this.db_tasks = r.message || [];
				this.has_fetched = true;
				this.toggle_button_visibility();
				this.render_tasks(this.db_tasks);
			});
	}

	render_tasks(tasks) {
		this.body.empty();
		if (!tasks || tasks.length === 0) {
			this.body.append(`
				<div class="bg-tasks-null-state">
					<div class="text-center">
						<div class="title">${__("No background tasks")}</div>
						<div class="subtitle">${__(
							"Looks like there are no background tasks running or completed recently."
						)}</div>
					</div>
				</div>
			`);
		} else {
			tasks.forEach((task) => {
				this.body.append(this.get_task_html(task));
			});
		}

		this.body.append(`
			<a class="bg-task-footer">
				<div>${__("View All Tasks")}</div>
			</a>
		`);
	}

	get_task_html(task) {
		const status_colors = {
			Running: { bg: "bg-primary", color: "blue" },
			Completed: { bg: "bg-success", color: "green" },
			Failed: { bg: "bg-danger", color: "red" },
			Queued: { bg: "bg-warning", color: "amber" },
			Cancelled: { bg: "bg-secondary", color: "gray" },
		};

		const { bg: bg_class, color } = status_colors[task.status] || status_colors["Running"];
		let progress = task.progress || 0;

		let progress_bar = "";
		if (task.status === "Running") {
			let stage_html = `<div class="bg-task-stage">${frappe.utils.escape_html(
				task.stage || ""
			)}</div>`;

			let bar_html = "";
			if (task.show_progress_bar !== 0) {
				bar_html = `<div class="progress">
					<div class="progress-bar ${bg_class}" role="progressbar" style="width: ${progress}%;" aria-valuenow="${progress}" aria-valuemin="0" aria-valuemax="100"></div>
				</div>`;
			}

			progress_bar = `
				${stage_html}
				${bar_html}
			`;
		}

		const task_title = frappe.utils.escape_html(task.task_name || task.name);

		let cancel_btn = "";
		let cancellable_class = "";
		if (
			task.status === "Queued" ||
			(task.status === "Running" && task.allow_user_cancellation !== 0)
		) {
			cancellable_class = "cancellable";
			cancel_btn = `
				<button class="btn btn-xs btn-cancel-task" data-task-id="${task.task_id}">
					${__("Cancel")}
				</button>
			`;
		}

		let retry_btn = "";
		let retryable_class = "";
		if (
			(task.status === "Failed" || task.status === "Cancelled") &&
			task.allow_user_retry !== 0
		) {
			retryable_class = "retryable";
			retry_btn = `
				<button class="btn btn-xs btn-retry-task" data-task-id="${task.task_id}">
					${__("Retry")}
				</button>
			`;
		}

		return $(`<a class="bg-task-item ${cancellable_class} ${retryable_class}" data-name="${
			task.name
		}" data-task-id="${task.task_id}">
			<div class="bg-task-header">
				<div class="bg-task-title">
					<span>${task_title}</span>
				</div>
				<div class="bg-task-actions" style="display: flex; align-items: center; justify-content: flex-end; min-width: 60px; flex-shrink: 0;">
					${frappe.ui.badge.html({
						label: task.status,
						theme: color,
						css_class: "status-badge",
					})}
					${cancel_btn}
					${retry_btn}
				</div>
			</div>
			${progress_bar}
		</a>`);
	}
};
