var editArea;


/**
 *  UTF-8 list taken from http://www.utf8-chartable.de/unicode-utf8-table.pl?utf8=dec 
 */  
 

/*
var char_range_list={
"Basic Latin":"0021,007F",
"Latin-1 Supplement":"0080,00FF",
"Latin Extended-A":"0100,017F",
"Latin Extended-B":"0180,024F",
"IPA Extensions":"0250,02AF",
"Spacing Modifier Letters":"02B0,02FF",

"Combining Diacritical Marks":"0300,036F",
"Greek and Coptic":"0370,03FF",
"Cyrillic":"0400,04FF",
"Cyrillic Supplement":"0500,052F",
"Armenian":"0530,058F",
"Hebrew":"0590,05FF",
"Arabic":"0600,06FF",
"Syriac":"0700,074F",
"Arabic Supplement":"0750,077F",

"Thaana":"0780,07BF",
"Devanagari":"0900,097F",
"Bengali":"0980,09FF",
"Gurmukhi":"0A00,0A7F",
"Gujarati":"0A80,0AFF",
"Oriya":"0B00,0B7F",
"Tamil":"0B80,0BFF",
"Telugu":"0C00,0C7F",
"Kannada":"0C80,0CFF",

"Malayalam":"0D00,0D7F",
"Sinhala":"0D80,0DFF",
"Thai":"0E00,0E7F",
"Lao":"0E80,0EFF",
"Tibetan":"0F00,0FFF",
"Myanmar":"1000,109F",
"Georgian":"10A0,10FF",
"Hangul Jamo":"1100,11FF",
"Ethiopic":"1200,137F",

"Ethiopic Supplement":"1380,139F",
"Cherokee":"13A0,13FF",
"Unified Canadian Aboriginal Syllabics":"1400,167F",
"Ogham":"1680,169F",
"Runic":"16A0,16FF",
"Tagalog":"1700,171F",
"Hanunoo":"1720,173F",
"Buhid":"1740,175F",
"Tagbanwa":"1760,177F",

"Khmer":"1780,17FF",
"Mongolian":"1800,18AF",
"Limbu":"1900,194F",
"Tai Le":"1950,197F",
"New Tai Lue":"1980,19DF",
"Khmer Symbols":"19E0,19FF",
"Buginese":"1A00,1A1F",
"Phonetic Extensions":"1D00,1D7F",
"Phonetic Extensions Supplement":"1D80,1DBF",

"Combining Diacritical Marks Supplement":"1DC0,1DFF",
"Latin Extended Additional":"1E00,1EFF",
"Greek Extended":"1F00,1FFF",
"General Punctuation":"2000,206F",
"Superscripts and Subscripts":"2070,209F",
"Currency Symbols":"20A0,20CF",
"Combining Diacritical Marks for Symbols":"20D0,20FF",
"Letterlike Symbols":"2100,214F",
"Number Forms":"2150,218F",

"Arrows":"2190,21FF",
"Mathematical Operators":"2200,22FF",
"Miscellaneous Technical":"2300,23FF",
"Control Pictures":"2400,243F",
"Optical Character Recognition":"2440,245F",
"Enclosed Alphanumerics":"2460,24FF",
"Box Drawing":"2500,257F",
"Block Elements":"2580,259F",
"Geometric Shapes":"25A0,25FF",

"Miscellaneous Symbols":"2600,26FF",
"Dingbats":"2700,27BF",
"Miscellaneous Mathematical Symbols-A":"27C0,27EF",
"Supplemental Arrows-A":"27F0,27FF",
"Braille Patterns":"2800,28FF",
"Supplemental Arrows-B":"2900,297F",
"Miscellaneous Mathematical Symbols-B":"2980,29FF",
"Supplemental Mathematical Operators":"2A00,2AFF",
"Miscellaneous Symbols and Arrows":"2B00,2BFF",

"Glagolitic":"2C00,2C5F",
"Coptic":"2C80,2CFF",
"Georgian Supplement":"2D00,2D2F",
"Tifinagh":"2D30,2D7F",
"Ethiopic Extended":"2D80,2DDF",
"Supplemental Punctuation":"2E00,2E7F",
"CJK Radicals Supplement":"2E80,2EFF",
"Kangxi Radicals":"2F00,2FDF",
"Ideographic Description Characters":"2FF0,2FFF",

"CJK Symbols and Punctuation":"3000,303F",
"Hiragana":"3040,309F",
"Katakana":"30A0,30FF",
"Bopomofo":"3100,312F",
"Hangul Compatibility Jamo":"3130,318F",
"Kanbun":"3190,319F",
"Bopomofo Extended":"31A0,31BF",
"CJK Strokes":"31C0,31EF",
"Katakana Phonetic Extensions":"31F0,31FF",

"Enclosed CJK Letters and Months":"3200,32FF",
"CJK Compatibility":"3300,33FF",
"CJK Unified Ideographs Extension A":"3400,4DBF",
"Yijing Hexagram Symbols":"4DC0,4DFF",
"CJK Unified Ideographs":"4E00,9FFF",
"Yi Syllables":"A000,A48F",
"Yi Radicals":"A490,A4CF",
"Modifier Tone Letters":"A700,A71F",
"Syloti Nagri":"A800,A82F",

"Hangul Syllables":"AC00,D7AF",
"High Surrogates":"D800,DB7F",
"High Private Use Surrogates":"DB80,DBFF",
"Low Surrogates":"DC00,DFFF",
"Private Use Area":"E000,F8FF",
"CJK Compatibility Ideographs":"F900,FAFF",
"Alphabetic Presentation Forms":"FB00,FB4F",
"Arabic Presentation Forms-A":"FB50,FDFF",
"Variation Selectors":"FE00,FE0F",

"Vertical Forms":"FE10,FE1F",
"Combining Half Marks":"FE20,FE2F",
"CJK Compatibility Forms":"FE30,FE4F",
"Small Form Variants":"FE50,FE6F",
"Arabic Presentation Forms-B":"FE70,FEFF",
"Halfwidth and Fullwidth Forms":"FF00,FFEF",
"Specials":"FFF0,FFFF",
"Linear B Syllabary":"10000,1007F",
"Linear B Ideograms":"10080,100FF",

"Aegean Numbers":"10100,1013F",
"Ancient Greek Numbers":"10140,1018F",
"Old Italic":"10300,1032F",
"Gothic":"10330,1034F",
"Ugaritic":"10380,1039F",
"Old Persian":"103A0,103DF",
"Deseret":"10400,1044F",
"Shavian":"10450,1047F",
"Osmanya":"10480,104AF",

"Cypriot Syllabary":"10800,1083F",
"Kharoshthi":"10A00,10A5F",
"Byzantine Musical Symbols":"1D000,1D0FF",
"Musical Symbols":"1D100,1D1FF",
"Ancient Greek Musical Notation":"1D200,1D24F",
"Tai Xuan Jing Symbols":"1D300,1D35F",
"Mathematical Alphanumeric Symbols":"1D400,1D7FF",
"CJK Unified Ideographs Extension B":"20000,2A6DF",
"CJK Compatibility Ideographs Supplement":"2F800,2FA1F",
"Tags":"E0000,E007F",
"Variation Selectors Supplement":"E0100,E01EF"
};
*/
var char_range_list={
"Aegean Numbers":"10100,1013F",
"Alphabetic Presentation Forms":"FB00,FB4F",
"Ancient Greek Musical Notation":"1D200,1D24F",
"Ancient Greek Numbers":"10140,1018F",
"Arabic":"0600,06FF",
"Arabic Presentation Forms-A":"FB50,FDFF",
"Arabic Presentation Forms-B":"FE70,FEFF",
"Arabic Supplement":"0750,077F",
"Armenian":"0530,058F",
"Arrows":"2190,21FF",
"Basic Latin":"0020,007F",
"Bengali":"0980,09FF",
"Block Elements":"2580,259F",
"Bopomofo Extended":"31A0,31BF",
"Bopomofo":"3100,312F",
"Box Drawing":"2500,257F",
"Braille Patterns":"2800,28FF",
"Buginese":"1A00,1A1F",
"Buhid":"1740,175F",
"Byzantine Musical Symbols":"1D000,1D0FF",
"CJK Compatibility Forms":"FE30,FE4F",
"CJK Compatibility Ideographs Supplement":"2F800,2FA1F",
"CJK Compatibility Ideographs":"F900,FAFF",
"CJK Compatibility":"3300,33FF",
"CJK Radicals Supplement":"2E80,2EFF",
"CJK Strokes":"31C0,31EF",
"CJK Symbols and Punctuation":"3000,303F",
"CJK Unified Ideographs Extension A":"3400,4DBF",
"CJK Unified Ideographs Extension B":"20000,2A6DF",
"CJK Unified Ideographs":"4E00,9FFF",
"Cherokee":"13A0,13FF",
"Combining Diacritical Marks Supplement":"1DC0,1DFF",
"Combining Diacritical Marks for Symbols":"20D0,20FF",
"Combining Diacritical Marks":"0300,036F",
"Combining Half Marks":"FE20,FE2F",
"Control Pictures":"2400,243F",
"Coptic":"2C80,2CFF",
"Currency Symbols":"20A0,20CF",
"Cypriot Syllabary":"10800,1083F",
"Cyrillic Supplement":"0500,052F",
"Cyrillic":"0400,04FF",
"Deseret":"10400,1044F",
"Devanagari":"0900,097F",
"Dingbats":"2700,27BF",
"Enclosed Alphanumerics":"2460,24FF",
"Enclosed CJK Letters and Months":"3200,32FF",
"Ethiopic Extended":"2D80,2DDF",
"Ethiopic Supplement":"1380,139F",
"Ethiopic":"1200,137F",
"General Punctuation":"2000,206F",
"Geometric Shapes":"25A0,25FF",
"Georgian Supplement":"2D00,2D2F",
"Georgian":"10A0,10FF",
"Glagolitic":"2C00,2C5F",
"Gothic":"10330,1034F",
"Greek Extended":"1F00,1FFF",
"Greek and Coptic":"0370,03FF",
"Gujarati":"0A80,0AFF",
"Gurmukhi":"0A00,0A7F",
"Halfwidth and Fullwidth Forms":"FF00,FFEF",
"Hangul Compatibility Jamo":"3130,318F",
"Hangul Jamo":"1100,11FF",
"Hangul Syllables":"AC00,D7AF",
"Hanunoo":"1720,173F",
"Hebrew":"0590,05FF",
"High Private Use Surrogates":"DB80,DBFF",
"High Surrogates":"D800,DB7F",
"Hiragana":"3040,309F",
"IPA Extensions":"0250,02AF",
"Ideographic Description Characters":"2FF0,2FFF",
"Kanbun":"3190,319F",
"Kangxi Radicals":"2F00,2FDF",
"Kannada":"0C80,0CFF",
"Katakana Phonetic Extensions":"31F0,31FF",
"Katakana":"30A0,30FF",
"Kharoshthi":"10A00,10A5F",
"Khmer Symbols":"19E0,19FF",
"Khmer":"1780,17FF",
"Lao":"0E80,0EFF",
"Latin Extended Additional":"1E00,1EFF",
"Latin Extended-A":"0100,017F",
"Latin Extended-B":"0180,024F",
"Latin-1 Supplement":"0080,00FF",
"Letterlike Symbols":"2100,214F",
"Limbu":"1900,194F",
"Linear B Ideograms":"10080,100FF",
"Linear B Syllabary":"10000,1007F",
"Low Surrogates":"DC00,DFFF",
"Malayalam":"0D00,0D7F",
"Mathematical Alphanumeric Symbols":"1D400,1D7FF",
"Mathematical Operators":"2200,22FF",
"Miscellaneous Mathematical Symbols-A":"27C0,27EF",
"Miscellaneous Mathematical Symbols-B":"2980,29FF",
"Miscellaneous Symbols and Arrows":"2B00,2BFF",
"Miscellaneous Symbols":"2600,26FF",
"Miscellaneous Technical":"2300,23FF",
"Modifier Tone Letters":"A700,A71F",
"Mongolian":"1800,18AF",
"Musical Symbols":"1D100,1D1FF",
"Myanmar":"1000,109F",
"New Tai Lue":"1980,19DF",
"Number Forms":"2150,218F",
"Ogham":"1680,169F",
"Old Italic":"10300,1032F",
"Old Persian":"103A0,103DF",
"Optical Character Recognition":"2440,245F",
"Oriya":"0B00,0B7F",
"Osmanya":"10480,104AF",
"Phonetic Extensions Supplement":"1D80,1DBF",
"Phonetic Extensions":"1D00,1D7F",
"Private Use Area":"E000,F8FF",
"Runic":"16A0,16FF",
"Shavian":"10450,1047F",
"Sinhala":"0D80,0DFF",
"Small Form Variants":"FE50,FE6F",
"Spacing Modifier Letters":"02B0,02FF",
"Specials":"FFF0,FFFF",
"Superscripts and Subscripts":"2070,209F",
"Supplemental Arrows-A":"27F0,27FF",
"Supplemental Arrows-B":"2900,297F",
"Supplemental Mathematical Operators":"2A00,2AFF",
"Supplemental Punctuation":"2E00,2E7F",
"Syloti Nagri":"A800,A82F",
"Syriac":"0700,074F",
"Tagalog":"1700,171F",
"Tagbanwa":"1760,177F",
"Tags":"E0000,E007F",
"Tai Le":"1950,197F",
"Tai Xuan Jing Symbols":"1D300,1D35F",
"Tamil":"0B80,0BFF",
"Telugu":"0C00,0C7F",
"Thaana":"0780,07BF",
"Thai":"0E00,0E7F",
"Tibetan":"0F00,0FFF",
"Tifinagh":"2D30,2D7F",
"Ugaritic":"10380,1039F",
"Unified Canadian Aboriginal Syllabics":"1400,167F",
"Variation Selectors Supplement":"E0100,E01EF",
"Variation Selectors":"FE00,FE0F",
"Vertical Forms":"FE10,FE1F",
"Yi Radicals":"A490,A4CF",
"Yi Syllables":"A000,A48F",
"Yijing Hexagram Symbols":"4DC0,4DFF"
};

var insert="charmap_insert";

function map_load(){
	editArea=opener.editArea;
	// translate the document
	insert= editArea.get_translation(insert, "word");
	//alert(document.title);
	document.title= editArea.get_translation(document.title, "template");
	document.body.innerHTML= editArea.get_translation(document.body.innerHTML, "template");
	//document.title= editArea.get_translation(document.getElementBytitle, "template");
	
	var selected_lang=opener.EditArea_charmap.default_language.toLowerCase();
	var selected=0;
	
	var select= document.getElementById("select_range")
	for(var i in char_range_list){
		if(i.toLowerCase()==selected_lang)
			selected=select.options.length;
		select.options[select.options.length]=new Option(i, char_range_list[i]);
	}
	select.options[selected].selected=true;
/*	start=0;
	end=127;
	content="";
	for(var i=start; i<end; i++){
		content+="&#"+i+"; ";
	}
	document.getElementById("char_list").innerHTML=content;*/
	renderCharMapHTML();
}


function renderCharMapHTML() {
	range= document.getElementById("select_range").value.split(",");

	start= parseInt(range[0],16);
	end= parseInt(range[1],16);
	var charsPerRow = 20, tdWidth=20, tdHeight=20;
	html="";
	for (var i=start; i<end; i++) {
		html+="<a class='char' onmouseover='previewChar(\""+ i + "\");' onclick='insertChar(\""+ i + "\");' title='"+ insert +"'>"+ String.fromCharCode(i) +"</a>";
	}
	document.getElementById("char_list").innerHTML= html;
	document.getElementById("preview_char").innerHTML="";
}

function previewChar(i){
	document.getElementById("preview_char").innerHTML= String.fromCharCode(i);
	document.getElementById("preview_code").innerHTML= "&amp;#"+ i +";";
}

function insertChar(i){
	opener.parent.editAreaLoader.setSelectedText(editArea.id, String.fromCharCode( i));
	range= opener.parent.editAreaLoader.getSelectionRange(editArea.id);
	opener.parent.editAreaLoader.setSelectionRange(editArea.id, range["end"], range["end"]);
	window.focus();
}
