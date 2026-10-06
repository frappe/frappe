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
		const $content = $(`<div class="flex flex-col gap-4 p-4"></div>`).appendTo(this.$body);
		$content.append(
			`<p class="text-p-sm text-ink-gray-5 max-w-lg m-0">${__(
				"Workspaces this site edited before the upgrade, as recorded in their version history. Restoring writes the edit as a customization, so the workspace shows it again at its usual address."
			)}</p>`
		);

		if (!rows.length) {
			$content.append(
				frappe.ui.empty_state({
					icon: "history",
					title: __("Nothing to restore"),
					description: frappe.boot.developer_mode
						? __(
								"This site is in developer mode, so edits to standard workspaces belong to the app's JSON and there is nothing to restore."
						  )
						: __("No pre-upgrade edits to standard workspaces were found."),
					css_class: "border border-outline-gray-2 rounded-lg",
				})
			);
			return;
		}

		const $list = $(`<div class="border border-outline-gray-2 rounded-lg"></div>`);
		rows.forEach((row, i) => {
			const $row = this.render_row(row);
			if (i) $row.addClass("border-t border-outline-gray-2");
			$list.append($row);
		});
		$content.append($list);
	}

	render_row(row) {
		const state = STATES[row.state];
		const escape = frappe.utils.escape_html;
		const details = [
			__(row.module),
			this.describe(row.summary),
			__("edited {0} by {1}", [
				frappe.datetime.prettyDate(row.last_edited_on),
				frappe.user_info(row.last_edited_by).fullname,
			]),
		];
		const $row = $(`
			<div class="flex items-center gap-4 px-4 py-3">
				<div class="flex flex-col gap-1 flex-1 min-w-0">
					<div class="flex items-center gap-2">
						<span class="text-base-medium text-ink-gray-8 truncate">${escape(__(row.title))}</span>
						${frappe.ui.badge.html({ label: state.label, theme: state.theme, size: "sm" })}
					</div>
					<div class="text-sm text-ink-gray-5 truncate">${escape(details.join(" · "))}</div>
					${this.render_warnings(row.warnings)}
				</div>
				<div class="flex items-center gap-2 shrink-0"></div>
			</div>
		`);
		const $actions = $row.children().last();
		if (state.action) {
			$actions.append(
				frappe.ui.button({
					label: state.action,
					onclick: () => this.restore(row),
				})
			);
		}
		if (row.state === "Restored") {
			$actions.append(
				frappe.ui.button({
					label: __("Visit"),
					icon_right: "arrow-up-right",
					onclick: () => frappe.set_route("desk", frappe.router.slug(row.workspace)),
				})
			);
		}
		return $row;
	}

	describe(summary) {
		const parts = [__("{0} blocks", [summary.blocks])];
		for (const [label, count] of Object.entries(summary.widgets || {})) {
			parts.push(__("{0} {1}", [count, label]));
		}
		if (summary.roles) {
			parts.push(__("{0} role changes", [summary.roles]));
		}
		return parts.join(", ");
	}

	render_warnings(warnings) {
		if (!warnings?.length) return "";
		const items = warnings
			.map(
				(w) =>
					`<li class="flex items-center gap-1.5">${frappe.utils.icon(
						"triangle-alert",
						"xs"
					)}<span>${w}</span></li>`
			)
			.join("");
		return `<ul class="list-none flex flex-col gap-1 p-0 m-0 text-sm text-ink-amber-6">${items}</ul>`;
	}

	restore(row) {
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
				() => resolve(this.call_restore(row)),
				() => resolve()
			);
		});
	}

	call_restore(row) {
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
