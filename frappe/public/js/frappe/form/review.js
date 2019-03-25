// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.ui.form");

frappe.ui.form.Review = class Review {
	constructor({parent, frm}) {
		this.parent = parent;
		this.frm = frm;
		this.make_review_container();
		this.add_review_button();
	}
	make_review_container() {
		this.$wrapper = this.parent.append(`
			<ul class="list-unstyled sidebar-menu">
				<li class="divider"></li>
				<li class="h6 shared-with-label">${__('Reviews')}</li>
				<li class="review-list"></li>
			</ul>
		`);
	}
	add_review_button() {
		this.review_list_wrapper = this.$wrapper.find('.review-list');

		Object.keys(frappe.boot.user_info).forEach((user) => {
			this.review_list_wrapper.append(`
				<span class="review-pill">
					${frappe.avatar(user)}
					<span class="text-muted">
						${Math.floor(Math.random() * 100) + 1}
					</span>
				</span>
			`);
		});

		this.review_list_wrapper.append(`
			<span class="avatar avatar-small avatar-empty share-doc-btn cursor-pointer" title="${__("Review")}">
				<i class="octicon octicon-plus text-muted" style="position: relative; left: 4.5px;"></i>
			</span>
		`);

		this.review_list_wrapper.find('.share-doc-btn').click(() => this.show());

	}
	get_involved_users() {
		const user_fields = this.frm.meta.fields
			.filter(d => d.fieldtype === 'Link' && d.options === 'User')
			.map(d => d.fieldname);

		user_fields.push('owner');
		let involved_users = user_fields.map(field => this.frm.doc[field]);

		const docinfo = this.frm.get_docinfo();

		involved_users.concat(docinfo.communications.map(d => d.sender && d.delivery_status==='sent'));
		involved_users.concat(docinfo.comments.map(d => d.owner));
		involved_users.concat(docinfo.versions.map(d => d.owner));
		involved_users.concat(docinfo.assignments.map(d => d.owner));

		involved_users = [...new Set(involved_users)];
		return involved_users.filter(Boolean);
	}
	show() {
		const review_dialog = new frappe.ui.Dialog({
			'title': __('Review'),
			'fields': [{
				fieldname: 'to_user',
				fieldtype: 'Select',
				label: __('To User'),
				options: this.get_involved_users(),
				default: this.frm.doc.owner
			}, {
				fieldname: 'action',
				fieldtype: 'Select',
				label: __('Action'),
				options: [{
					'label': __('Appreciate'),
					'value': 'Appreciation'
				}, {
					'label': __('Criticize'),
					'value': 'Criticism'
				}],
				default: 'Appreciation'
			}, {
				fieldname: 'points',
				fieldtype: 'Int',
				label: __('Points'),
				reqd: 1,
				description: __(`Currently you have ${frappe.boot.review_points} review points`)
			}, {
				fieldtype: 'Small Text',
				fieldname: 'reason',
				reqd: 1,
				label: __('Reason')
			}],
			primary_action: (values) => {
				if (values.points >= frappe.boot.review_points) {
					return frappe.msgprint(__('You do not have enough points'));
				}
				// Add energy point log -- need api for that
				frappe.xcall('frappe.social.doctype.energy_point_log.energy_point_log.review', {
					doc: {
						doctype: this.frm.doc.doctype,
						name: this.frm.doc.name,
					},
					to_user: values.to_user,
					points: values.points,
					reason: values.reason
				}).then(() => {
					review_dialog.hide();
					review_dialog.clear();
				});
				// deduct review points from the user
				// Alert
			},
			primary_action_label: __('Send')
		});
		review_dialog.show();
	}
};
