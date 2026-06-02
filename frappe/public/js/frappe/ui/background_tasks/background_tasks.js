frappe.ui.BackgroundTasks = class BackgroundTasks {
	constructor(opts) {
		this.wrapper = opts?.wrapper || $(".standard-items-sections");
		this.db_tasks = [];
		this.has_fetched = false;
		this.make();
	}

	make() {
		this.button = this.wrapper.find(".sidebar-background-tasks");
		this.dropdown = this.wrapper.find(".dropdown-background-tasks");
		this.dropdown_list = this.dropdown.find(".background-tasks-list");
		this.header_items = this.dropdown_list.find(".bg-tasks-header-items");
		this.header_actions = this.dropdown_list.find(".bg-tasks-header-actions");
		this.body = this.dropdown_list.find(".background-tasks-body");

		this.setup_headers();
		this.setup_dropdown_events();
		this.update_tasks();
	}

	toggle_button_visibility() {
		this.button.toggleClass("hidden", !this.db_tasks || this.db_tasks.length === 0);
	}

	setup_headers() {
		$(`<span class="close-bg-tasks-dialogue pull-right" style="cursor: pointer; color: var(--text-muted);">
			${frappe.utils.icon("x", "sm")}
		</span>`)
			.on("click", () => {
				this.dropdown.addClass("hidden");
			})
			.appendTo(this.header_actions);

		let header_title = $(`<div class="bg-tasks-category">
			${__("Background Tasks")}
		</div>`);
		this.header_items.append(header_title);
	}

	setup_dropdown_events() {
		this.wrapper.find(".sidebar-background-tasks").on("click", (e) => {
			if (!this.dropdown.hasClass("hidden")) {
				if (!this.has_fetched) {
					this.update_tasks();
				} else {
					// Re-render to sync the DOM with in-memory state that might have updated while hidden
					this.render_tasks(this.db_tasks);
				}
			}
		});

		$(document).on("click", (e) => {
			const isInsideBtn =
				$(e.target).closest(".standard-items-sections .sidebar-background-tasks").length >
				0;
			const isInsideDropdown =
				$(e.target).closest(".dropdown-background-tasks .background-tasks-list").length >
				0;

			if (!isInsideBtn && !isInsideDropdown) {
				this.dropdown.addClass("hidden");
			}
		});

		this.dropdown.on("click", ".bg-task-item", (e) => {
			let name = $(e.currentTarget).data("name");
			if (name) {
				frappe.set_route("background-task", name);
			}
			this.dropdown.addClass("hidden");
		});

		this.dropdown.on("click", ".bg-task-footer", () => {
			frappe.set_route("background-task");
			this.dropdown.addClass("hidden");
		});

		this.dropdown.on("click", ".btn-cancel-task", (e) => {
			e.preventDefault();
			e.stopPropagation();
			let task_id = $(e.currentTarget).data("task-id");
			frappe.call({
				method: "frappe.core.doctype.background_task.background_task.stop_task",
				args: { task_id: task_id },
			});
		});

		this.dropdown.on("click", ".btn-retry-task", (e) => {
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

				if (!this.dropdown.hasClass("hidden")) {
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
							if (!this.dropdown.hasClass("hidden")) {
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
			Queued: { bg: "bg-warning", color: "orange" },
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

		return $(`<a class="bg-task-item ${cancellable_class} ${retryable_class}" data-name="${task.name}" data-task-id="${task.task_id}">
			<div class="bg-task-header">
				<div class="bg-task-title">
					<span>${task_title}</span>
				</div>
				<div class="bg-task-actions" style="display: flex; align-items: center; justify-content: flex-end; min-width: 60px; flex-shrink: 0;">
					<div class="indicator-pill ${color} no-indicator-dot whitespace-nowrap status-badge">
						${task.status}
					</div>
					${cancel_btn}
					${retry_btn}
				</div>
			</div>
			${progress_bar}
		</a>`);
	}
};
