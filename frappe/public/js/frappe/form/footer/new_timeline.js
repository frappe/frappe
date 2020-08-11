// Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.NewTimeline = class {
	constructor(opts) {
		Object.assign(this, opts);
		this.doc_info = this.frm && this.frm.get_docinfo() || {};
		this.make();
	}

	make() {
		this.timeline_wrapper = $(`<div class="new-timeline">`);
		this.parent.replaceWith(this.timeline_wrapper);
		this.timeline_items = [];
		this.render_timeline_items();
	}

	refresh() {
		this.render_timeline_items();
	}

	add_action_button() {

	}

	render_timeline_items() {
		this.timeline_wrapper.empty();
		this.timeline_items = [];
		this.prepare_timeline_contents();

		this.timeline_items.sort((item1, item2) => new Date(item1.creation) - new Date(item2.creation));
		this.timeline_items.forEach(this.add_timeline_item.bind(this));
	}

	prepare_timeline_contents() {
		this.timeline_items.push(...this.get_view_timeline_contents());
		this.timeline_items.push(...this.get_communication_timeline_contents());
		this.timeline_items.push(...this.get_comment_timeline_contents());
		this.timeline_items.push(...this.get_energy_point_timeline_contents());
		// shared
		// milestones
		// versions
		// attachments
	}

	add_timeline_item(item) {
		let timeline_item = this.get_timeline_item(item);
		this.timeline_wrapper.prepend(timeline_item);
		return timeline_item;
	}

	get_timeline_item(item) {
		const timeline_item = $(`
			<div class="timeline-item">
				<div class="timeline-indicator">
					${frappe.utils.icon(item.icon, 'md')}
				</div>
				<div class="timeline-content ${item.card ? 'frappe-card' : ''}"></div>
			</div>
		`);
		timeline_item.find('.timeline-content').append(item.content);
		if (!item.hide_timestamp) {
			timeline_item.find('.timeline-content').append(`<div>${comment_when(item.creation)}</div>`);
		}
		return timeline_item;
	}

	get_view_timeline_contents() {
		let view_timeline_contents = [];
		(this.doc_info.views || []).forEach(view => {
			let view_content = `
				<div>
					<a href="${frappe.utils.get_form_link('View Log', view.name)}">
						${__("{0} viewed", [frappe.user.full_name(view.owner).bold()])}
					</a>
				</div>
			`;
			view_timeline_contents.push({
				icon: 'view',
				creation: view.creation,
				content: view_content,
			});
		});
		return view_timeline_contents;
	}

	get_communication_timeline_contents() {
		let communication_timeline_contents = [];
		(this.doc_info.communications|| []).forEach(communication => {
			let communication_content =  $(frappe.render_template('timeline_email', { doc: communication }));
			this.setup_reply(communication_content);
			communication_content.find(".timeline-email-content").append(communication.content);
			communication_timeline_contents.push({
				icon: 'mail',
				creation: communication.creation,
				card: true,
				content: communication_content,
			});
		});
		return communication_timeline_contents;
	}

	get_comment_timeline_contents() {
		let comment_timeline_contents = [];
		(this.doc_info.comments || []).forEach(comment => {
			comment_timeline_contents.push({
				icon: 'mail',
				creation: comment.creation,
				content: comment.content,
			});
		});
		return comment_timeline_contents;
	}

	get_version_timeline_contents() {
		let version_timeline_contents = [];
		(this.doc_info.versions || []).forEach(version => {
			version_timeline_contents.push({
				icon: 'mail',
				creation: version.creation,
				content: version.content,
			});
		});
		return version_timeline_contents;
	}

	get_energy_point_timeline_contents() {
		let energy_point_timeline_contents = [];
		(this.doc_info.energy_point_logs || []).forEach(log => {
			energy_point_timeline_contents.push({
				icon: 'review',
				creation: log.creation,
				content: frappe.energy_points.format_form_log(log)
			});
		});
		return energy_point_timeline_contents;
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