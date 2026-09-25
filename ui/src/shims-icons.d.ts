// `~icons/<collection>/<name>` are virtual modules resolved by unplugin-icons at
// the consumer's Vite build (enable via `frappeui({ lucideIcons: true })`). This
// package ships as source, so declare the module shape here for editor/type support.
declare module "~icons/*" {
  import type { FunctionalComponent, SVGAttributes } from "vue";
  const component: FunctionalComponent<SVGAttributes>;
  export default component;
}
