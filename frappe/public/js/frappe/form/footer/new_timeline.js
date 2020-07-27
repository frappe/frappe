// Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.NewTimeline = class {
	constructor(opts) {
		Object.assign(this, opts);
		this.make();
	}

	make() {
		this.timeline_wrapper = $(`<div class="new-timeline">`);
		this.parent.replaceWith(this.timeline_wrapper);
		this.timeline_items = [];
		this.render_timeline_items();
	}

	refresh() {

	}

	add_action_button() {

	}

	render_timeline_items() {
		this.prepare_timeline_contents();

		this.timeline_items.sort((item1, item2) => item1.creation - item2.creation);
		this.timeline_items.forEach(item => {
			this.timeline_wrapper.append(this.get_timeline_item(item));
		});
	}

	prepare_timeline_contents() {
		const doc_info = this.frm.get_docinfo();
		doc_info.views.forEach(view => {
			this.timeline_items.push({
				icon: 'view',
				creation: view.creation,
				content: this.get_view_content(view),
			});
		});

		Array.from(Array(5)).forEach(() => {
			this.timeline_items.push({
				icon: ['mail', 'view', 'call', 'edit'][Math.floor(Math.random() * 4)],
				creation: Date(),
				content: `Lorem Ipsum is simply dummy text of the printing and
					typesetting industry. Lorem Ipsum has been the industry's
					standard dummy text ever since the 1500s,`,
				card: true
			});
		});

		doc_info.communications.forEach(communication => {
			this.timeline_items.push({
				icon: 'mail',
				creation: communication.creation,
				card: true,
				content: this.get_communication_content(communication),
			});
		});
	}

	get_timeline_item(item) {
		const timeline_item = $(`
			<div class="timeline-item">
				<div class="timeline-indicator">
					${frappe.utils.icon(item.icon, 'md')}
				</div>
				<div class="timeline-content ${item.card ? 'frappe-card' : ''}">
				</div>
			</div>
		`);
		timeline_item.find('.timeline-content').append(item.content);
		return timeline_item;
	}

	get_view_content(doc) {
		return `
			<div>
				<a href="${frappe.utils.get_form_link('View Log', doc.name)}">
					${__("{0} viewed", [frappe.user.full_name(doc.owner).bold()])}
				</a>
				- ${comment_when(doc.creation)}
			</div>
		`;
	}

	get_communication_content(doc) {
		let item =  $(frappe.render_template('timeline_email', { doc }));
		this.setup_reply(item);
		item.find(".timeline-email-content").append(doc.content);
		return item;
	}

	setup_reply(communication_box) {
		let actions = communication_box.find('.actions');
		let reply = $(`<a class="reply">${frappe.utils.icon('reply', 'md')}</a>`).click(e => {
			console.log(e);
		});
		let reply_all = $(`<a class="reply-all">${frappe.utils.icon('reply-all', 'md')}</a>`).click(e => {
			console.log(e);
		});
		actions.append(reply);
		actions.append(reply_all);
	}
};