import AttachControl from "./components/controls/AttachControl.vue";
import AttachImageControl from "./components/controls/AttachImageControl.vue";
import AutocompleteControl from "./components/controls/AutocompleteControl.vue";
import BarcodeControl from "./components/controls/BarcodeControl.vue";
import ButtonControl from "./components/controls/ButtonControl.vue";
import CheckControl from "./components/controls/CheckControl.vue";
import CodeControl from "./components/controls/CodeControl.vue";
import ColorControl from "./components/controls/ColorControl.vue";
import CurrencyControl from "./components/controls/CurrencyControl.vue";
import DataControl from "./components/controls/DataControl.vue";
import DateControl from "./components/controls/DateControl.vue";
import DatetimeControl from "./components/controls/DatetimeControl.vue";
import DurationControl from "./components/controls/DurationControl.vue";
import DynamicLinkControl from "./components/controls/DynamicLinkControl.vue";
import FloatControl from "./components/controls/FloatControl.vue";
import GeolocationControl from "./components/controls/GeolocationControl.vue";
import HeadingControl from "./components/controls/HeadingControl.vue";
import HTMLControl from "./components/controls/HTMLControl.vue";
import HTMLEditorControl from "./components/controls/HTMLEditorControl.vue";
import IconControl from "./components/controls/IconControl.vue";
import ImageControl from "./components/controls/ImageControl.vue";
import IntControl from "./components/controls/IntControl.vue";
import JSONControl from "./components/controls/JSONControl.vue";
import LinkControl from "./components/controls/LinkControl.vue";
import LongTextControl from "./components/controls/LongTextControl.vue";
import MarkdownEditorControl from "./components/controls/MarkdownEditorControl.vue";
import PasswordControl from "./components/controls/PasswordControl.vue";
import PercentControl from "./components/controls/PercentControl.vue";
import PhoneControl from "./components/controls/PhoneControl.vue";
import ReadOnlyControl from "./components/controls/ReadOnlyControl.vue";
import RatingControl from "./components/controls/RatingControl.vue";
import SelectControl from "./components/controls/SelectControl.vue";
import SignatureControl from "./components/controls/SignatureControl.vue";
import SmallTextControl from "./components/controls/SmallTextControl.vue";
import TableControl from "./components/controls/TableControl.vue";
import TableMultiSelectControl from "./components/controls/TableMultiSelectControl.vue";
import TextControl from "./components/controls/TextControl.vue";
import TextEditorControl from "./components/controls/TextEditorControl.vue";
import TimeControl from "./components/controls/TimeControl.vue";

export function registerGlobalComponents(app) {
	app.component("AttachControl", AttachControl)
		.component("AttachImageControl", AttachImageControl)
		.component("AutocompleteControl", AutocompleteControl)
		.component("BarcodeControl", BarcodeControl)
		.component("ButtonControl", ButtonControl)
		.component("CheckControl", CheckControl)
		.component("CodeControl", CodeControl)
		.component("ColorControl", ColorControl)
		.component("CurrencyControl", CurrencyControl)
		.component("DataControl", DataControl)
		.component("DateControl", DateControl)
		.component("DatetimeControl", DatetimeControl)
		.component("DurationControl", DurationControl)
		.component("DynamicLinkControl", DynamicLinkControl)
		.component("FloatControl", FloatControl)
		.component("GeolocationControl", GeolocationControl)
		.component("HeadingControl", HeadingControl)
		.component("HTMLControl", HTMLControl)
		.component("HTMLEditorControl", HTMLEditorControl)
		.component("IconControl", IconControl)
		.component("ImageControl", ImageControl)
		.component("IntControl", IntControl)
		.component("JSONControl", JSONControl)
		.component("LinkControl", LinkControl)
		.component("LongTextControl", LongTextControl)
		.component("MarkdownEditorControl", MarkdownEditorControl)
		.component("PasswordControl", PasswordControl)
		.component("PercentControl", PercentControl)
		.component("PhoneControl", PhoneControl)
		.component("ReadOnlyControl", ReadOnlyControl)
		.component("RatingControl", RatingControl)
		.component("SelectControl", SelectControl)
		.component("SignatureControl", SignatureControl)
		.component("SmallTextControl", SmallTextControl)
		.component("TableControl", TableControl)
		.component("TableMultiSelectControl", TableMultiSelectControl)
		.component("TextControl", TextControl)
		.component("TextEditorControl", TextEditorControl)
		.component("TimeControl", TimeControl);
}
