const WIDTH_QUERY = /^(not all and\s*)?(\((?:min|max)-width:\s*[\d.]+px\))$/;

export default {
	name: "island-container-queries",
	config: () => ({
		css: {
			postcss: {
				plugins: [
					{
						postcssPlugin: "island-container-queries",
						AtRule: {
							media(rule) {
								const match = rule.params.match(WIDTH_QUERY);
								if (!match) return;
								rule.name = "container";
								rule.params = `${match[1] ? "not " : ""}${match[2]}`;
							},
						},
					},
				],
			},
		},
	}),
};
