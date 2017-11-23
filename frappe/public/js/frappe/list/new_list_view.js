frappe.provide('frappe.views');

const default_settings = {
	doctype: null,
	start: 0,
	page_length: 20,
	data: []
}

frappe.views.ListView = class ListView {
	constructor(opts) {
		Object.assign(this, default_settings, opts);
		console.log(this);

		// load last view
		this.build_last_route();
		frappe.set_route(this.route);

		this.setup_defaults();

		// make view
		this.setup_page_head();
	}

	build_last_route() {
		//TODO: remember to load last kanban board and last email inbox from user_settings
		this.route = frappe.get_route();
		const user_settings = frappe.get_user_settings(this.doctype);

		if (this.route.length === 2) {
			// routed to List/{doctype}
			//   -> route to last_view [OR]
			//   -> route to List/{doctype}/List
			const last_view = frappe.views.is_valid(user_settings.last_view)
				&& user_settings.last_view;

			this.route.push(last_view || 'List');
		}
	}

	setup_defaults() {
		this.page = this.parent.page;
		this.page_name = 'List/' + this.doctype;
		this.page_title = this.page_title || __(this.doctype);
	}

	setup_page_head() {
		this.page.set_title(this.page_title);
		this.menu = new ListMenu(this);
	}
}

class ListMenu {
	constructor(list_view) {
		this.list_view = list_view;
		this.doctype = this.list_view.doctype;
		this.page = this.list_view.page;
		this.setup();
	}

	setup() {
		const doctype = this.doctype;
		// Refresh button for large screens
		this.page.set_secondary_action(__('Refresh'), () => {
			this.refresh(true);
		}, 'octicon octicon-sync').addClass('hidden-xs');

		// Refresh button as menu item in small screens
		this.page.add_menu_item(__('Refresh'), () => {
			this.refresh(true);
		}, 'octicon octicon-sync').addClass('visible-xs');

		if (frappe.model.can_import(doctype)) {
			this.page.add_menu_item(__('Import'), () => {
				frappe.set_route('data-import-tool', { doctype });
			}, true);
		}
		if (frappe.model.can_set_user_permissions(doctype)) {
			this.page.add_menu_item(__('User Permissions'), () => {
				frappe.set_route('List', 'User Permission', { allow: doctype });
			}, true);
		}
		if (frappe.user_roles.includes('System Manager')) {
			this.page.add_menu_item(__('Role Permissions Manager'), () => {
				frappe.set_route('permission-manager', { doctype });
			}, true);
			this.page.add_menu_item(__('Customize'), () => {
				frappe.set_route('Form', 'Customize Form', { doc_type: doctype });
			}, true);
		}

		this.make_bulk_assignment();
		if (frappe.model.can_print(doctype)) {
			this.make_bulk_printing();
		}

		// add to desktop
		this.page.add_menu_item(__('Add to Desktop'), () => {
			frappe.add_to_desktop(doctype, doctype);
		}, true);

		if (frappe.user.has_role('System Manager') && frappe.boot.developer_mode === 1) {
			// edit doctype
			this.page.add_menu_item(__('Edit DocType'), () => {
				frappe.set_route('Form', 'DocType', doctype);
			}, true);
		}
	}

	make_bulk_assignment() {
		// bulk assignment
		this.page.add_menu_item(__('Assign To'), () => {
			const docnames = this.list_view.get_checked_items().map(doc => doc.name);

			if (docnames.length > 0) {
				const dialog = new frappe.ui.form.AssignToDialog({
					obj: this.list_view,
					method: 'frappe.desk.form.assign_to.add_multiple',
					doctype: this.doctype,
					docname: docnames,
					bulk_assign: true,
					re_assign: true,
					callback: () => this.list_view.refresh(true)
				});
				dialog.clear();
				dialog.show();
			}
			else {
				frappe.msgprint(__('Select records for assignment'))
			}
		}, true);

	}

	make_bulk_printing() {
		const print_settings = frappe.model.get_doc(':Print Settings', 'Print Settings');
		const allow_print_for_draft = cint(print_settings.allow_print_for_draft);
		const is_submittable = frappe.model.is_submittable(this.doctype);
		const allow_print_for_cancelled = cint(print_settings.allow_print_for_cancelled);

		this.page.add_menu_item(__('Print'), () => {
			const items = this.list_view.get_checked_items();

			const valid_docs = items.filter(doc => {
					return !is_submittable || doc.docstatus === 1 ||
						(allow_print_for_cancelled && doc.docstatus == 2) ||
						(allow_print_for_draft && doc.docstatus == 0) ||
						frappe.user.has_role('Administrator')
				}).map(doc => doc.name);

			var invalid_docs = items.filter(doc => !valid_docs.includes(doc.name));

			if (invalid_docs.length > 0) {
				frappe.msgprint(__('You selected Draft or Cancelled documents'));
				return;
			}

			if (valid_docs.length > 0) {
				const dialog = new frappe.ui.Dialog({
					title: __('Print Documents'),
					fields: [
						{ 'fieldtype': 'Check', 'label': __('With Letterhead'), 'fieldname': 'with_letterhead' },
						{ 'fieldtype': 'Select', 'label': __('Print Format'), 'fieldname': 'print_sel', options: frappe.meta.get_print_formats(this.doctype) },
					]
				});

				dialog.set_primary_action(__('Print'), args => {
					if (!args) return;
					const default_print_format = frappe.get_meta(this.doctype).default_print_format;
					const with_letterhead = args.with_letterhead ? 1 : 0;
					const print_format = args.print_sel ? args.print_sel : default_print_format;
					const json_string = JSON.stringify(valid_docs);

					const w = window.open('/api/method/frappe.utils.print_format.download_multi_pdf?'
						+ 'doctype=' + encodeURIComponent(this.doctype)
						+ '&name=' + encodeURIComponent(json_string)
						+ '&format=' + encodeURIComponent(print_format)
						+ '&no_letterhead=' + (with_letterhead ? '0' : '1'));
					if (!w) {
						frappe.msgprint(__('Please enable pop-ups')); return;
					}
				});

				dialog.show();
			}
			else {
				frappe.msgprint(__('Select atleast 1 record for printing'))
			}
		}, true);
	}
}

// utility function to validate view modes
frappe.views.view_modes = ['List', 'Gantt', 'Kanban', 'Calendar', 'Image', 'Inbox', 'Report'];
frappe.views.is_valid = view_mode => frappe.views.view_modes.includes(view_mode);
