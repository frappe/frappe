// Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.ui");

frappe.ui.color_map = {
	red: ["#ffc4c4", "#ff8989", "#ff4d4d", "#a83333"],
	brown: ["#ffe8cd", "#ffd19c", "#ffb868", "#a87945"],
	orange: ["#ffd2c2", "#ffa685", "#ff7846", "#a85b5b"],
	peach: ["#ffd7d7", "#ffb1b1", "#ff8989", "#a84f2e"],
	yellow: ["#fffacd", "#fff168", "#fff69c", "#a89f45"],
	yellowgreen: ["#ebf8cc", "#d9f399", "#c5ec63", "#7b933d"],
	green: ["#cef6d1", "#9deca2", "#6be273", "#428b46"],
	cyan: ["#d2f8ed", "#a4f3dd", "#77ecca", "#49937e"],
	skyblue: ["#d2f1ff", "#a6e4ff", "#78d6ff", "#4f8ea8"],
	blue: ["#d2d2ff", "#a3a3ff", "#7575ff", "#4d4da8"],
	purple: ["#dac7ff", "#b592ff", "#8e58ff", "#5e3aa8"],
	pink: ["#f8d4f8", "#f3aaf0", "#ec7dea", "#934f92"]
};

frappe.ui.color = {
	get: function(color_name, shade) {
		if(color_name && shade) return this.get_color_shade(color_name, shade);
		if(color_name) return this.get_color_shade(color_name, 'default');
		return frappe.ui.color_map;
	},
	get_color: function(color_name) {
		const color_names = Object.keys(frappe.ui.color_map);
		if(color_names.includes(color_name)) {
			return frappe.ui.color_map[color_name];
		} else {
			// eslint-disable-next-line
			console.warn(`'color_name' can be one of ${color_names} and not ${color_name}`);
		}
	},
	get_color_shade: function(color_name, shade) {
		const shades = {
			'default': 2,
			'light': 1,
			'extra-light': 0,
			'dark': 3
		};

		if(Object.keys(shades).includes(shade)) {
			return frappe.ui.color_map[color_name][shades[shade]];
		} else {
			// eslint-disable-next-line
			console.warn(`'shade' can be one of ${Object.keys(shades)} and not ${shade}`);
		}
	},
	all: function() {
		return Object.values(frappe.ui.color_map)
			.reduce((acc, curr) => acc.concat(curr) , []);
	},
	names: function() {
		return Object.keys(frappe.ui.color_map);
	},
	is_standard: function(color_name) {
		if(!color_name) return false;
		if(color_name.startsWith('#')) {
			return this.all().includes(color_name);
		}
		return this.names().includes(color_name);
	},
	get_color_name: function(hex) {
		for (const key in frappe.ui.color_map) {
			const colors = frappe.ui.color_map[key];
			if (colors.includes(hex)) return key;
		}
	},
	get_contrast_color: function(hex) {
		if(!this.validate_hex(hex)) {
			return;
		}
		if(!this.is_standard(hex)) {
			const brightness = this.brightness(hex);
			if(brightness < 128) {
				return this.lighten(hex, 0.5);
			}
			return this.lighten(hex, -0.5);
		}

		const color_name = this.get_color_name(hex);
		const colors = this.get_color(color_name);
		const shade_value = colors.indexOf(hex);
		if(shade_value <= 1) {
			return this.get(color_name, 'dark');
		}
		return this.get(color_name, 'extra-light');
	},

	validate_hex: function(hex) {
		// https://stackoverflow.com/a/8027444/5353542
		return /(^#[0-9A-F]{6}$)|(^#[0-9A-F]{3}$)/i.test(hex);
	},

	lighten(color, percent) {
		// https://stackoverflow.com/a/13542669/5353542
		var f = parseInt(color.slice(1), 16),
			t = percent < 0 ? 0 : 255,
			p = percent < 0 ? percent * -1 : percent,
			R = f >> 16,
			G = f >> 8 & 0x00FF,
			B = f & 0x0000FF;
		return "#" +
			(0x1000000 +
				(Math.round((t - R) * p) + R) *
				0x10000 +
				(Math.round((t - G) * p) + G) *
				0x100 + (Math.round((t - B) * p) + B)
			).toString(16).slice(1);
	},

	hex_to_rgb(hex) {
		if(hex.startsWith('#')) {
			hex = hex.substring(1);
		}
		const r = parseInt(hex.substring(0, 2), 16);
		const g = parseInt(hex.substring(2, 4), 16);
		const b = parseInt(hex.substring(4, 6), 16);
		return {r, g, b};
	},

	brightness(hex) {
		const rgb = this.hex_to_rgb(hex);
		// https://www.w3.org/TR/AERT#color-contrast
		// 255 - brightest (#fff)
		// 0 - darkest (#000)
		return (rgb.r * 299 + rgb.g * 587 + rgb.b * 114) / 1000;
	}
};
