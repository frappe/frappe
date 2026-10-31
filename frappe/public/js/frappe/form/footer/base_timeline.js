// Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

class BaseTimeline {
	constructor(opts) {
		Object.assign(this, opts);
		this.make();
	}

	make() {
		this.timeline_wrapper = $(`<div class="new-timeline">`);
		this.wrapper = this.timeline_wrapper;
		this.timeline_items_wrapper = $(`<div class="timeline-items">`);
		this.timeline_actions_wrapper = $(`
			<div class="timeline-items timeline-actions">
				<div class="timeline-item">
					<div class="timeline-content action-buttons"></div>
				</div>
			</div>
		`);

		this.timeline_wrapper.append(this.timeline_actions_wrapper);
		this.timeline_actions_wrapper.hide();
		this.timeline_wrapper.append(this.timeline_items_wrapper);

		this.parent.replaceWith(this.timeline_wrapper);
		this.timeline_items = [];
	}

	refresh() {
		this.render_timeline_items();
	}

	add_action_button(label, action, icon = null, btn_class = null) {
		let icon_element = icon ? frappe.utils.icon(icon, "xs") : null;
		this.timeline_actions_wrapper.show();
		let action_btn = $(`<button class="btn btn-xs ${btn_class || "btn-default"} action-btn">
			${icon_element}
			${label}
		</button>`);
		action_btn.click(action);
		this.timeline_actions_wrapper.find(".action-buttons").append(action_btn);
		return action_btn;
	}

	render_timeline_items() {
		this.timeline_items_wrapper.empty();
		this.timeline_items = [];
		this.doc_info = (this.frm && this.frm.get_docinfo()) || {};
		let response = this.prepare_timeline_contents();
		if (response instanceof Promise) {
			response.then(() => this.add_sorted_timeline_items());
		} else {
			this.add_sorted_timeline_items();
		}
	}

	add_sorted_timeline_items() {
		this.timeline_items.sort(
			(item1, item2) => new Date(item2.creation) - new Date(item1.creation)
		);
		this.group_timeline_items(this.timeline_items).forEach(this.add_timeline_item.bind(this));
	}

	prepare_timeline_contents() {
		//
	}

	group_timeline_items(items) {
		return items;
	}

	get_timestamp_text(creation) {
		return cint(frappe.boot.user.show_absolute_datetime_in_timeline) ||
			frappe.defaults.is_enabled("show_absolute_datetime_in_timeline")
			? frappe.datetime.str_to_user(creation)
			: comment_when(creation);
	}

	add_timeline_item(item, append_at_the_end = false) {
		let timeline_item = this.get_timeline_item(item);
		if (append_at_the_end) {
			this.timeline_items_wrapper.append(timeline_item);
		} else {
			this.timeline_items_wrapper.prepend(timeline_item);
		}
		return timeline_item;
	}

	add_timeline_items(items, append_at_the_end = false) {
		items.forEach((item) => this.add_timeline_item(item, append_at_the_end));
	}

	add_timeline_items_based_on_creation(items) {
		items.forEach((item) => {
			const older = this.timeline_items_wrapper
				.children(".timeline-item")
				.toArray()
				.find((el) => {
					const creation = el.dataset.timestamp;
					return creation && new Date(creation) < new Date(item.creation);
				});
			older
				? $(older).before(this.get_timeline_item(item))
				: this.timeline_items_wrapper.append(this.get_timeline_item(item));
		});
	}

	get_timeline_item(item) {
		// item can have content*, creation*,
		// user, timeline_badge, icon, icon_size,
		// hide_timestamp, show_timestamp, is_card
		const timeline_item = $(`<div class="timeline-item">`);

		if (item.name == "load-more") {
			timeline_item.append(
				`<div class="timeline-load-more">
					<button class="btn btn-default btn-sm btn-load-more">
						<span>${item.content}</span>
					</button>
				</div>`
			);
			timeline_item.find(".btn-load-more").on("click", async () => {
				let more_items = await this.get_more_communication_timeline_contents();
				timeline_item.remove();
				this.add_timeline_items_based_on_creation(more_items);
			});
			return timeline_item;
		}

		timeline_item.attr({
			"data-doctype": item.doctype,
			"data-name": item.name,
			"data-timestamp": item.creation,
		});
		if (item.user) {
			timeline_item.append(this.get_timeline_avatar(item));
		} else if (item.icon) {
			timeline_item.append(`
				<div class="timeline-badge" title='${item.title || frappe.utils.to_title_case(item.icon)}'>
					${frappe.utils.icon(item.icon, item.icon_size || "md", item.icon_class || "")}
				</div>
			`);
		} else if (item.timeline_badge) {
			timeline_item.append(item.timeline_badge);
		} else {
			timeline_item.append(`<div class="timeline-dot">`);
		}

		const timeline_body = $(`<div class="timeline-body">`).appendTo(timeline_item);
		const timeline_content = $(
			`<div class="timeline-content ${item.is_card ? "frappe-card" : ""}">`
		).appendTo(timeline_body);
		timeline_content.append(item.content);

		const show_timestamp = item.show_timestamp ?? (!item.hide_timestamp && !item.is_card);
		if (show_timestamp && item.creation) {
			const exact_time = moment(frappe.datetime.convert_to_user_tz(item.creation)).format(
				"lll"
			);
			timeline_body.append(
				`<div class="timeline-timestamp" title="${exact_time}">${this.get_timestamp_text(
					item.creation
				)}</div>`
			);
		}

		if (item.id) {
			timeline_content.attr("id", item.id);
		}

		return timeline_item;
	}

	get_timeline_avatar(item) {
		if (item.icon) {
			return `<div class="timeline-badge" title="${
				item.title || frappe.utils.to_title_case(item.icon)
			}">${frappe.utils.icon(item.icon, "md", item.icon_class || "")}</div>`;
		}
		return `<div class="timeline-avatar">${frappe.avatar(item.user, "avatar-small")}</div>`;
	}
}

frappe.ui.BaseTimeline = BaseTimeline;
export default BaseTimeline;
