import "./jquery-bootstrap";
import "./frappe/provide.js";
import "./frappe/format.js";
import "./frappe/utils/datatype.js";
import "./frappe/utils/common.js";
import "./frappe/translate.js";
import "../../website/js/website.js";

// Floating Message
frappe.utils.icon = function (
	icon_name,
	size = "sm",
	icon_class = "",
	icon_style = "",
	svg_class = ""
) {
	let size_class = "";
	let is_espresso = icon_name.startsWith("es-");

	icon_name = is_espresso ? `${"#" + icon_name}` : `${"#icon-" + icon_name}`;
	if (typeof size == "object") {
		icon_style += ` width: ${size.width}; height: ${size.height}`;
	} else {
		size_class = `icon-${size}`;
	}
	return `<svg class="${
		is_espresso
			? icon_name.startsWith("es-solid")
				? "es-icon es-solid"
				: "es-icon es-line"
			: "icon"
	} ${svg_class} ${size_class}" style="${icon_style}" aria-hidden="true">
		<use class="${icon_class}" href="${icon_name}"></use>
	</svg>`;
};
frappe.show_alert = frappe.toast = function (data, seconds = 7, actions = {}) {
	let indicator_icon_map = {
		orange: "solid-warning",
		yellow: "solid-warning",
		blue: "solid-info",
		green: "solid-success",
		red: "solid-error",
	};

	if (typeof data === "string") {
		data = { message: data };
	}

	if (!$("#dialog-container").length) {
		$('<div id="dialog-container"><div id="alert-container"></div></div>').appendTo("body");
	}

	let icon;
	if (data.indicator) {
		icon = indicator_icon_map[data.indicator.toLowerCase()] || "solid-" + data.indicator;
	} else {
		icon = "solid-info";
	}

	const indicator = data.indicator || "blue";

	const div = $(`
		<div class="alert desk-alert ${indicator}" role="alert">
			<div class="alert-message-container">
				<div class="alert-title-container">
					<div>${frappe.utils.icon(icon, "lg")}</div>
					<div class="alert-message">${data.message}</div>
				</div>
				<div class="alert-subtitle">${data.subtitle || ""}</div>
			</div>
			<div class="alert-body" style="display: none"></div>
			<a class="close">${frappe.utils.icon("close-alt")}</a>
		</div>
	`);

	div.hide().appendTo("#alert-container").show();

	if (data.body) {
		div.find(".alert-body").show().html(data.body);
	}

	div.find(".close, button").click(function () {
		div.addClass("out");
		setTimeout(() => div.remove(), 800);
		return false;
	});

	Object.keys(actions).map((key) => {
		div.find(`[data-action=${key}]`).on("click", actions[key]);
	});

	if (seconds > 2) {
		// Delay for animation
		seconds = seconds - 0.8;
	}

	setTimeout(() => {
		div.addClass("out");
		setTimeout(() => div.remove(), 800);
		return false;
	}, seconds * 1000);

	return div;
};
frappe.msgprint = function (msg, title, is_minimizable) {
	msg.forEach((m) => {
		frappe.show_alert(JSON.parse(m));
	});
};
window.msgprint = frappe.msgprint;
