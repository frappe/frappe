import AttachControl from "../form_builder/components/controls/AttachControl.vue";
import ButtonControl from "../form_builder/components/controls/ButtonControl.vue";
import CheckControl from "../form_builder/components/controls/CheckControl.vue";
import CodeControl from "../form_builder/components/controls/CodeControl.vue";
import DataControl from "../form_builder/components/controls/DataControl.vue";
import GeolocationControl from "../form_builder/components/controls/GeolocationControl.vue";
import ImageControl from "../form_builder/components/controls/ImageControl.vue";
import LinkControl from "../form_builder/components/controls/LinkControl.vue";
import RatingControl from "../form_builder/components/controls/RatingControl.vue";
import SelectControl from "../form_builder/components/controls/SelectControl.vue";
import SignatureControl from "../form_builder/components/controls/SignatureControl.vue";
import TableControl from "../form_builder/components/controls/TableControl.vue";
import TextControl from "../form_builder/components/controls/TextControl.vue";
import TextEditorControl from "../form_builder/components/controls/TextEditorControl.vue";

export function registerGlobalComponents(app) {
	app.component("AttachControl", AttachControl)
		.component("AttachImageControl", AttachControl)
		.component("AutocompleteControl", DataControl)
		.component("BarcodeControl", DataControl)
		.component("ButtonControl", ButtonControl)
		.component("CheckControl", CheckControl)
		.component("CodeControl", CodeControl)
		.component("ColorControl", DataControl)
		.component("CurrencyControl", DataControl)
		.component("DataControl", DataControl)
		.component("DateControl", DataControl)
		.component("DatetimeControl", DataControl)
		.component("DurationControl", DataControl)
		.component("DynamicLinkControl", DataControl)
		.component("FloatControl", DataControl)
		.component("GeolocationControl", GeolocationControl)
		.component("HeadingControl", ButtonControl)
		.component("HTMLControl", DataControl)
		.component("HTMLEditorControl", CodeControl)
		.component("IconControl", DataControl)
		.component("ImageControl", ImageControl)
		.component("IntControl", DataControl)
		.component("JSONControl", CodeControl)
		.component("LinkControl", LinkControl)
		.component("LongTextControl", TextControl)
		.component("MarkdownEditorControl", CodeControl)
		.component("PasswordControl", DataControl)
		.component("PercentControl", DataControl)
		.component("PhoneControl", DataControl)
		.component("ReadOnlyControl", DataControl)
		.component("RatingControl", RatingControl)
		.component("SelectControl", SelectControl)
		.component("SignatureControl", SignatureControl)
		.component("SmallTextControl", TextControl)
		.component("TableControl", TableControl)
		.component("TableMultiSelectControl", DataControl)
		.component("TextControl", TextControl)
		.component("TextEditorControl", TextEditorControl)
		.component("TimeControl", DataControl);
}
