export default {
	get_hue(rgb) {
		return this.get_hsv(rgb)[0];
	},

	get_hsv(rgb) {
		if (typeof rgb === "string") {
			if (rgb.startsWith("#")) {
				rgb = this.hex_to_rgb_values(rgb);
			} else {
				rgb = this.get_rgb_values(rgb);
			}
		}
		return this.rgb_to_hsv(...rgb);
	},

	get_rgb_values(rgb_string) {
		return rgb_string
			.replace(/[()rgb\s]/g, "")
			.split(",")
			.map((s) => parseInt(s));
	},

	rgb_to_hsv(r, g, b) {
		r /= 255;
		g /= 255;
		b /= 255;

		let max = Math.max(r, g, b),
			min = Math.min(r, g, b);
		let h,
			s,
			v = max;

		let d = max - min;
		s = max == 0 ? 0 : d / max;

		if (max == min) {
			h = 0; // achromatic
		} else {
			switch (max) {
				case r:
					h = (g - b) / d + (g < b ? 6 : 0);
					break;
				case g:
					h = (b - r) / d + 2;
					break;
				case b:
					h = (r - g) / d + 4;
					break;
			}

			h /= 6;
		}
		return [Math.round(h * 360), Math.round(s * 100), Math.round(v * 100)];
	},

	component_to_hex(c) {
		const hex = c.toString(16);
		return hex.length == 1 ? "0" + hex : hex;
	},

	rgb_to_hex(r, g, b) {
		return (
			"#" + this.component_to_hex(r) + this.component_to_hex(g) + this.component_to_hex(b)
		);
	},

	hex_to_rgb_values(hex) {
		const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
		return [parseInt(result[1], 16), parseInt(result[2], 16), parseInt(result[3], 16)];
	},

	hsv_to_hex(h, s, v) {
		s /= 100;
		v /= 100;
		h /= 360;

		let r, g, b;
		let i = Math.floor(h * 6);
		let f = h * 6 - i;
		let p = v * (1 - s);
		let q = v * (1 - f * s);
		let t = v * (1 - (1 - f) * s);

		switch (i % 6) {
			case 0:
				(r = v), (g = t), (b = p);
				break;
			case 1:
				(r = q), (g = v), (b = p);
				break;
			case 2:
				(r = p), (g = v), (b = t);
				break;
			case 3:
				(r = p), (g = q), (b = v);
				break;
			case 4:
				(r = t), (g = p), (b = v);
				break;
			case 5:
				(r = v), (g = p), (b = q);
				break;
		}
		r = Math.round(r * 255);
		g = Math.round(g * 255);
		b = Math.round(b * 255);
		return this.rgb_to_hex(r, g, b);
	},

	clamp(min, val, max) {
		return val > max ? max : val < min ? min : val;
	},
};
