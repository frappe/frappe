// The Vue SFC plugin, configured the one way an island may compile a template.
//
// The compiler drops comments, always. A template that keeps its comments
// renders the component as a fragment, so every fallthrough attribute (`class`,
// `style`, listeners) lands on nothing, with no warning. 33 components in
// frappe-ui open their template with a comment. The compiler otherwise takes
// this from the build mode, which would make a development island and a shipped
// one render differently.

/**
 * @param {Function} vue  `@vitejs/plugin-vue`, from the app's tree
 * @param {Object} [options]
 * @returns {import('vite').Plugin[]}
 */
export function islandVue(vue, options = {}) {
	return vue({
		...options,
		template: {
			...options.template,
			compilerOptions: { ...options.template?.compilerOptions, comments: false },
		},
	});
}
