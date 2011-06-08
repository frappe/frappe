	/*EditArea.prototype.comment_or_quotes= function(v0, v1, v2, v3, v4,v5,v6,v7,v8,v9, v10){
		new_class="quotes";
		if(v6 && v6 != undefined && v6!="")
			new_class="comments";
		return "µ__"+ new_class +"__µ"+v0+"µ_END_µ";

	};*/
	
/*	EditArea.prototype.htmlTag= function(v0, v1, v2, v3, v4,v5,v6,v7,v8,v9, v10){
		res="<span class=htmlTag>"+v2;
		alert("v2: "+v2+" v3: "+v3);
		tab=v3.split("=");
		attributes="";
		if(tab.length>1){
			attributes="<span class=attribute>"+tab[0]+"</span>=";
			for(i=1; i<tab.length-1; i++){
				cut=tab[i].lastIndexOf("&nbsp;");				
				attributes+="<span class=attributeVal>"+tab[i].substr(0,cut)+"</span>";
				attributes+="<span class=attribute>"+tab[i].substr(cut)+"</span>=";
			}
			attributes+="<span class=attributeVal>"+tab[tab.length-1]+"</span>";
		}		
		res+=attributes+v5+"</span>";
		return res;		
	};*/
	
	// determine if the selected text if a comment or a quoted text
	EditArea.prototype.comment_or_quote= function(){
		var new_class="", close_tag="", sy, arg, i;
		sy 		= parent.editAreaLoader.syntax[editArea.current_code_lang];
		arg		= EditArea.prototype.comment_or_quote.arguments[0];
		
		for( i in sy["quotes"] ){
			if(arg.indexOf(i)==0){
				new_class="quotesmarks";
				close_tag=sy["quotes"][i];
			}
		}
		if(new_class.length==0)
		{
			for(var i in sy["comments"]){
				if( arg.indexOf(i)==0 ){
					new_class="comments";
					close_tag=sy["comments"][i];
				}
			}
		}
		// for single line comment the \n must not be included in the span tags
		if(close_tag=="\n"){
			return "µ__"+ new_class +"__µ"+ arg.replace(/(\r?\n)?$/m, "µ_END_µ$1");
		}else{
			// the closing tag must be set only if the comment or quotes is closed 
			reg= new RegExp(parent.editAreaLoader.get_escaped_regexp(close_tag)+"$", "m");
			if( arg.search(reg)!=-1 )
				return "µ__"+ new_class +"__µ"+ arg +"µ_END_µ";
			else
				return "µ__"+ new_class +"__µ"+ arg;
		}
	};
	
/*
	// apply special tags arround text to highlight
	EditArea.prototype.custom_highlight= function(){
		res= EditArea.prototype.custom_highlight.arguments[1]+"µ__"+ editArea.reg_exp_span_tag +"__µ" + EditArea.prototype.custom_highlight.arguments[2]+"µ_END_µ";
		if(EditArea.prototype.custom_highlight.arguments.length>5)
			res+= EditArea.prototype.custom_highlight.arguments[ EditArea.prototype.custom_highlight.arguments.length-3 ];
		return res;
	};
	*/
	
	// return identication that allow to know if revalidating only the text line won't make the syntax go mad
	EditArea.prototype.get_syntax_trace= function(text){
		if(this.settings["syntax"].length>0 && parent.editAreaLoader.syntax[this.settings["syntax"]]["syntax_trace_regexp"])
			return text.replace(parent.editAreaLoader.syntax[this.settings["syntax"]]["syntax_trace_regexp"], "$3");
	};
	
		
	EditArea.prototype.colorize_text= function(text){
		//text="<div id='result' class='area' style='position: relative; z-index: 4; height: 500px; overflow: scroll;border: solid black 1px;'> ";
	  /*		
		if(this.isOpera){	
			// opera can't use pre element tabulation cause a tab=6 chars in the textarea and 8 chars in the pre 
			text= this.replace_tab(text);
		}*/
		
		text= " "+text; // for easier regExp
		
		/*if(this.do_html_tags)
			text= text.replace(/(<[a-z]+ [^>]*>)/gi, '[__htmlTag__]$1[_END_]');*/
		if(this.settings["syntax"].length>0)
			text= this.apply_syntax(text, this.settings["syntax"]);

		// remove the first space added
		return text.substr(1).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/µ_END_µ/g,"</span>").replace(/µ__([a-zA-Z0-9]+)__µ/g,"<span class='$1'>");
	};
	
	EditArea.prototype.apply_syntax= function(text, lang){
		var sy;
		this.current_code_lang=lang;
	
		if(!parent.editAreaLoader.syntax[lang])
			return text;
			
		sy = parent.editAreaLoader.syntax[lang];
		if(sy["custom_regexp"]['before']){
			for( var i in sy["custom_regexp"]['before']){
				var convert="$1µ__"+ sy["custom_regexp"]['before'][i]['class'] +"__µ$2µ_END_µ$3";
				text= text.replace(sy["custom_regexp"]['before'][i]['regexp'], convert);
			}
		}
		
		if(sy["comment_or_quote_reg_exp"]){
			//setTimeout("_$('debug_area').value=editArea.comment_or_quote_reg_exp;", 500);
			text= text.replace(sy["comment_or_quote_reg_exp"], this.comment_or_quote);
		}
		
		if(sy["keywords_reg_exp"]){
			for(var i in sy["keywords_reg_exp"]){	
				text= text.replace(sy["keywords_reg_exp"][i], 'µ__'+i+'__µ$2µ_END_µ');
			}			
		}
		
		if(sy["delimiters_reg_exp"]){
			text= text.replace(sy["delimiters_reg_exp"], 'µ__delimiters__µ$1µ_END_µ');
		}		
		
		if(sy["operators_reg_exp"]){
			text= text.replace(sy["operators_reg_exp"], 'µ__operators__µ$1µ_END_µ');
		}
		
		if(sy["custom_regexp"]['after']){
			for( var i in sy["custom_regexp"]['after']){
				var convert="$1µ__"+ sy["custom_regexp"]['after'][i]['class'] +"__µ$2µ_END_µ$3";
				text= text.replace(sy["custom_regexp"]['after'][i]['regexp'], convert);			
			}
		}
			
		return text;
	};
