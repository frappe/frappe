module.exports = {
	semi: false,
	tabWidth: 2,
	useTabs: true,
	printWidth: 110,
	bracketSpacing: true,
	singleAttributePerLine: false,
	arrowParens: "always",
	trailingComma: "all",
	plugins: [require.resolve("prettier-plugin-tailwindcss")],
	tailwindConfig: "./tailwind.config.js",
}
