// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.is_liked = function (doc) {
	return frappe.ui.get_liked_by(doc).includes(frappe.session.user);
};

frappe.ui.get_liked_by = function (doc) {
	return doc._liked_by ? JSON.parse(doc._liked_by) : [];
};

frappe.ui.toggle_like = function ($btn, doctype, name, callback) {
	const add = $btn.hasClass("not-liked") ? "Yes" : "No";
	// disable click
	$btn.css("pointer-events", "none");

	frappe.call({
		method: "frappe.desk.like.toggle_like",
		quiet: true,
		args: {
			doctype: doctype,
			name: name,
			add: add,
		},
		callback: function (r) {
			// renable click
			$btn.css("pointer-events", "auto");

			if (r.exc) {
				return;
			}

			$btn.toggleClass("not-liked", add === "No");
			$btn.toggleClass("liked", add === "Yes");

			// update in locals (form)
			const doc = locals[doctype] && locals[doctype][name];
			if (doc) {
				let liked_by = frappe.ui.get_liked_by(doc);

				if (add === "Yes" && !liked_by.includes(frappe.session.user)) {
					liked_by.push(frappe.session.user);
				}

				if (add === "No" && liked_by.includes(frappe.session.user)) {
					liked_by = liked_by.filter((user) => user !== frappe.session.user);
				}

				doc._liked_by = JSON.stringify(liked_by);
			}

			if (callback) {
				callback();
			}
		},
	});
};

frappe.ui.click_toggle_like = function () {
	console.warn("`frappe.ui.click_toggle_like` is deprecated and has no effect.");
};

frappe.ui.setup_like_popover = ($parent, selector) => {
	if (frappe.dom.is_touchscreen()) {
		return;
	}

	$parent.on("mouseover", selector, function () {
		const target_element = $(this);
		target_element.popover({
			animation: true,
			placement: "bottom",
			trigger: "manual",
			template: `<div class="liked-by-popover popover">
				<div class="arrow"></div>
				<div class="popover-body popover-content"></div>
			</div>`,
			content: () => {
				let liked_by = target_element.parents(".liked-by").attr("data-liked-by");
				liked_by = liked_by ? decodeURI(liked_by) : "[]";
				liked_by = JSON.parse(liked_by);

				if (!liked_by.length) {
					return "";
				}

				let liked_by_list = $(`<ul class="list-unstyled"></ul>`);

				// to show social profile of the user
				let link_base = "/app/user-profile/";

				liked_by.forEach((user) => {
					// append user list item
					liked_by_list.append(`
						<li data-user=${user}>${frappe.avatar(user, "avatar-xs")}
							<span>${frappe.user.full_name(user)}</span>
						</li>
					`);
				});

				liked_by_list.children("li").click((ev) => {
					let user = ev.currentTarget.dataset.user;
					target_element.popover("hide");
					frappe.set_route(link_base + user);
				});

				return liked_by_list;
			},
			html: true,
			container: "body",
		});

		target_element.popover("show");

		$(".popover").on("mouseleave", () => {
			target_element.popover("hide");
		});

		target_element.on("mouseout", () => {
			setTimeout(() => {
				if (!$(".popover:hover").length) {
					target_element.popover("hide");
				}
			}, 100);
		});
	});
};
