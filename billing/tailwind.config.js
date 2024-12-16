module.exports = {
	presets: [require('frappe-ui/src/utils/tailwind.config')],
	content: [
		'./index.html',
		'./src/**/*.{vue,js,ts,jsx,tsx}',
		'./node_modules/frappe-ui/src/components/**/*.{vue,js,ts,jsx,tsx}',
		'../node_modules/frappe-ui/src/components/**/*.{vue,js,ts,jsx,tsx}',
	],
	safelist: [
		{ pattern: /!(text|bg)-/, variants: ['hover', 'active'] },
		{ pattern: /^grid-cols-/ },
	],
	theme: {
		extend: {},
	},
	plugins: [],
}
