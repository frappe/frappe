import type { FormLayoutSchema } from "../../components/FormLayout/types";

/** Props for `<PanelLayout>`. The doc and the open sections are `v-model`s. */
export interface PanelLayoutProps {
  /** The same tabs → sections → columns → fields schema `FormLayout` renders. */
  layout: FormLayoutSchema;
}
