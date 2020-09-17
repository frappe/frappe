// Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

class BaseTimeline {
	constructor(opts) {
		Object.assign(this, opts);
		this.make();
	}

	make() {
		this.timeline_wrapper = $(`<div class="new-timeline">`);
		this.timeline_items_wrapper = $(`<div class="timeline-items">`);
		this.timeline_actions_wrapper = $(`
			<div class="timeline-actions">
				<div class="timeline-dot"></div>
			</div>
		`);

		this.timeline_wrapper.append(this.timeline_actions_wrapper);
		this.timeline_wrapper.append(this.timeline_items_wrapper);

		this.parent.replaceWith(this.timeline_wrapper);
		this.timeline_items = [];
	}

	refresh() {
		this.render_timeline_items();
	}

	add_action_button(label, action) {
		let action_btn = $(`<button class="btn btn-xs btn-default action-btn">${label}</button>`);
		action_btn.click(action);
		this.timeline_actions_wrapper.append(action_btn);
		return action_btn;
	}

	render_timeline_items() {
		this.timeline_items_wrapper.empty();
		this.timeline_items = [];
		this.doc_info = this.frm && this.frm.get_docinfo() || {};
		this.prepare_timeline_contents();

		this.timeline_items.sort((item1, item2) => new Date(item1.creation) - new Date(item2.creation));
		this.timeline_items.forEach(this.add_timeline_item.bind(this));
	}

	prepare_timeline_contents() {
		//
	}

	add_timeline_item(item) {
		let timeline_item = this.get_timeline_item(item);
		this.timeline_items_wrapper.prepend(timeline_item);
		return timeline_item;
	}

	get_timeline_item(item) {
		// item can have content*, creation*,
		// timeline_badge, icon, icon_size,
		// hide_timestamp, card
		const timeline_item = $(`<div class="timeline-item">`);

		if (item.icon) {
			timeline_item.append(`
				<div class="timeline-badge">
					${frappe.utils.icon(item.icon, item.icon_size || 'md')}
				</div>
			`);
		} else if (item.timeline_badge) {
			timeline_item.append(item.timeline_badge);
		} else {
			timeline_item.append(`<div class="timeline-dot">`);
		}

		timeline_item.append(`<div class="timeline-content ${item.card ? 'frappe-card' : ''}">`);
		timeline_item.find('.timeline-content').append(item.content);
		if (!item.hide_timestamp && !item.card) {
			timeline_item.find('.timeline-content').append(`<span> - ${comment_when(item.creation)}</span>`);
		}
		return timeline_item;
	}
}

export default BaseTimeline;