export default {
	default: [
		{
			divisor: 1.0e12,
			symbol: __("T", null, "Number system"),
		},
		{
			divisor: 1.0e9,
			symbol: __("B", null, "Number system"),
		},
		{
			divisor: 1.0e6,
			symbol: __("M", null, "Number system"),
		},
		{
			divisor: 1.0e3,
			symbol: __("K", null, "Number system"),
		},
	],
	indian: [
		{
			divisor: 1.0e7,
			symbol: __("Cr", null, "Number system"),
		},
		{
			divisor: 1.0e5,
			symbol: __("Lakh", null, "Number system"),
		},
		{
			divisor: 1.0e3,
			symbol: __("K", null, "Number system"),
		},
	],
	nepalese: [
		{
			divisor: 1.0e11,
			symbol: __("Kh", null, "Number system"), // 10^11 is read as 1 Kharba
		},
		{
			divisor: 1.0e9,
			symbol: __("Ar", null, "Number system"), // 10^9 is read as 1 Arba
		},
		{
			divisor: 1.0e7,
			symbol: __("Cr", null, "Number system"),
		},
		{
			divisor: 1.0e5,
			symbol: __("L", null, "Number system"),
		},
		{
			divisor: 1.0e3,
			symbol: __("K", null, "Number system"),
		},
	],
};
