import type { FormLayoutSchema } from "../../components/FormLayout/types";
import type { PanelSectionItem } from "../RecordPage/types";
import type { Surface } from "../RecordPage/surface";

/** Props for `<PanelLayout>`. The doc and the open sections are `v-model`s. */
export interface PanelLayoutProps {
  /** The same tabs → sections → columns → fields schema `FormLayout` renders. */
  layout: FormLayoutSchema;
  /** The record page's `panelSections` surface; scripts overlay the layout, never edit it. */
  surface?: Surface<PanelSectionItem>;
  /** The curated page a scripted section's component mounts with. */
  page?: any;
}
