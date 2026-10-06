frappe.pages["workspace-restore"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Restore Workspace"),
		single_column: true,
	});
	wrapper.workspace_restore = new WorkspaceRestore(page);
};

frappe.pages["workspace-restore"].on_page_show = function (wrapper) {
	wrapper.workspace_restore?.refresh();
};

const STATES = {
	Overwritten: { theme: "amber", label: __("Overwritten"), action: __("Restore") },
	"Not yet overwritten": {
		theme: "blue",
		label: __("Not yet overwritten"),
		action: __("Protect"),
	},
	Restored: { theme: "green", label: __("Restored"), action: null },
	"Customized since": {
		theme: "gray",
		label: __("Customized since"),
		action: __("Restore again"),
	},
};

class WorkspaceRestore {
	constructor(page) {
		this.page = page;
		this.$body = $(page.body);
	}

	refresh() {
		frappe
			.xcall(
				"frappe.desk.page.workspace_restore.workspace_restore.get_restorable_workspaces"
			)
			.then((rows) => this.render(rows));
	}

	render(rows) {
		this.$body.empty();
		this.$body.append(
			`<p class="text-muted">${__(
				"Workspaces this site edited before the upgrade, as recorded in their version history. Restoring writes the edit as a customization, so the workspace shows it again at its usual address."
			)}</p>`
		);

		if (!rows.length) {
			const reason = frappe.boot.developer_mode
				? __(
						"This site is in developer mode, so edits to standard workspaces belong to the app's JSON and there is nothing to restore."
				  )
				: __("No pre-upgrade edits to standard workspaces were found.");
			this.$body.append(`<p class="text-muted">${reason}</p>`);
			return;
		}

		const $table = $(`
			<table class="table table-sm">
				<thead>
					<tr>
						<th>${__("Workspace")}</th>
						<th>${__("Last edited")}</th>
						<th>${__("Changes")}</th>
						<th>${__("Status")}</th>
						<th></th>
					</tr>
				</thead>
				<tbody></tbody>
			</table>
		`);
		for (const row of rows) {
			$table.find("tbody").append(this.render_row(row));
		}
		this.$body.append($table);
	}

	render_row(row) {
		const state = STATES[row.state] || STATES.Overwritten;
		const $row = $(`
			<tr>
				<td>
					<div>${frappe.utils.escape_html(__(row.title))}</div>
					<div class="text-muted small">${frappe.utils.escape_html(__(row.module))}</div>
				</td>
				<td>
					<div>${frappe.datetime.comment_when(row.last_edited_on)}</div>
					<div class="text-muted small">${frappe.utils.escape_html(
						frappe.user_info(row.last_edited_by).fullname
					)}</div>
				</td>
				<td>
					<div>${this.describe(row.summary)}</div>
					${this.render_warnings(row.warnings)}
				</td>
				<td>${frappe.ui.badge.html({ label: state.label, theme: state.theme })}</td>
				<td class="text-right"></td>
			</tr>
		`);
		if (state.action) {
			$row.find("td:last").append(
				frappe.ui.button({
					label: state.action,
					variant: row.state === "Customized since" ? "subtle" : "solid",
					size: "sm",
					onclick: () => this.restore(row, state),
				})
			);
		}
		return $row;
	}

	describe(summary) {
		const parts = [__("{0} blocks", [summary.blocks])];
		for (const [type, count] of Object.entries(summary.widgets || {})) {
			parts.push(__("{0} added {1}", [count, __(type.replace("_", " "))]));
		}
		if (summary.roles) {
			parts.push(__("{0} role changes", [summary.roles]));
		}
		return frappe.utils.escape_html(parts.join(", "));
	}

	render_warnings(warnings) {
		if (!warnings?.length) return "";
		const items = warnings
			.map((w) => `<li>${frappe.utils.icon("alert-triangle", "xs")} ${w}</li>`)
			.join("");
		return `<ul class="list-unstyled text-muted small">${items}</ul>`;
	}

	restore(row, state) {
		const message =
			row.state === "Customized since"
				? __(
						"<b>{0}</b> has been customized on this site since the upgrade. Restoring replaces that customization with the pre-upgrade layout.",
						[__(row.title)]
				  )
				: __(
						"Restore the pre-upgrade layout of <b>{0}</b>? The layout becomes a site customization, so later layout changes from the app will not show until it is reset to standard.",
						[__(row.title)]
				  );
		return new Promise((resolve) => {
			frappe.confirm(
				message,
				() => resolve(this.call_restore(row, state)),
				() => resolve()
			);
		});
	}

	call_restore(row, state) {
		return frappe
			.xcall(
				"frappe.desk.page.workspace_restore.workspace_restore.restore_workspace_edits",
				{
					workspace: row.workspace,
				}
			)
			.then((payload) => {
				this.apply_payload(payload);
				frappe.show_alert({
					message: __("{0}: pre-upgrade edits restored", [__(row.title)]),
					indicator: "green",
				});
				if (payload.warnings?.length) {
					frappe.msgprint({
						title: __("Restored with limits"),
						message: `<ul>${payload.warnings
							.map((w) => `<li>${w}</li>`)
							.join("")}</ul>`,
						indicator: "orange",
					});
				}
				this.refresh();
			});
	}

	apply_payload(payload) {
		// Same swap the workspace manager does, so the next visit to the workspace in this
		// tab renders the restored layout without a hard refresh.
		if (frappe.workspace) {
			frappe.workspace.apply_manager_changes(payload);
			return;
		}
		frappe.boot.workspaces = payload.workspace_pages;
		if (payload.module_sidebars) frappe.boot.module_sidebars = payload.module_sidebars;
		if (payload.entity_module) frappe.boot.entity_module = payload.entity_module;
		if (payload.app_data) frappe.boot.app_data = payload.app_data;
	}
}
