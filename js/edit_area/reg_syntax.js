	EditAreaLoader.prototype.get_regexp= function(text_array){
		//res="( |=|\\n|\\r|\\[|\\(|µ|)(";
		res="(\\b)(";
		for(i=0; i<text_array.length; i++){
			if(i>0)
				res+="|";
			//res+="("+ tab_text[i] +")";
			//res+=tab_text[i].replace(/(\.|\?|\*|\+|\\|\(|\)|\[|\]|\{|\})/g, "\\$1");
			res+=this.get_escaped_regexp(text_array[i]);
		}
		//res+=")( |\\.|:|\\{|\\(|\\)|\\[|\\]|\'|\"|\\r|\\n|\\t|$)";
		res+=")(\\b)";
		reg= new RegExp(res);
		
		return res;
	};
	
	
	EditAreaLoader.prototype.get_escaped_regexp= function(str){
		return str.toString().replace(/(\.|\?|\*|\+|\\|\(|\)|\[|\]|\}|\{|\$|\^|\|)/g, "\\$1");
	};
	
	EditAreaLoader.prototype.init_syntax_regexp= function(){
		var lang_style= {};	
		for(var lang in this.load_syntax){
			if(!this.syntax[lang])	// init the regexp if not already initialized
			{
				this.syntax[lang]= {};
				this.syntax[lang]["keywords_reg_exp"]= {};
				this.keywords_reg_exp_nb=0;
			
				if(this.load_syntax[lang]['KEYWORDS']){
					param="g";
					if(this.load_syntax[lang]['KEYWORD_CASE_SENSITIVE']===false)
						param+="i";
					for(var i in this.load_syntax[lang]['KEYWORDS']){
						if(typeof(this.load_syntax[lang]['KEYWORDS'][i])=="function") continue;
						this.syntax[lang]["keywords_reg_exp"][i]= new RegExp(this.get_regexp( this.load_syntax[lang]['KEYWORDS'][i] ), param);
						this.keywords_reg_exp_nb++;
					}
				}
				
				if(this.load_syntax[lang]['OPERATORS']){
					var str="";
					var nb=0;
					for(var i in this.load_syntax[lang]['OPERATORS']){
						if(typeof(this.load_syntax[lang]['OPERATORS'][i])=="function") continue;
						if(nb>0)
							str+="|";				
						str+=this.get_escaped_regexp(this.load_syntax[lang]['OPERATORS'][i]);
						nb++;
					}
					if(str.length>0)
						this.syntax[lang]["operators_reg_exp"]= new RegExp("("+str+")","g");
				}
				
				if(this.load_syntax[lang]['DELIMITERS']){
					var str="";
					var nb=0;
					for(var i in this.load_syntax[lang]['DELIMITERS']){
						if(typeof(this.load_syntax[lang]['DELIMITERS'][i])=="function") continue;
						if(nb>0)
							str+="|";
						str+=this.get_escaped_regexp(this.load_syntax[lang]['DELIMITERS'][i]);
						nb++;
					}
					if(str.length>0)
						this.syntax[lang]["delimiters_reg_exp"]= new RegExp("("+str+")","g");
				}
				
				
		//		/(("(\\"|[^"])*"?)|('(\\'|[^'])*'?)|(//(.|\r|\t)*\n)|(/\*(.|\n|\r|\t)*\*/)|(<!--(.|\n|\r|\t)*-->))/gi
				var syntax_trace=[];
				
		//		/("(?:[^"\\]*(\\\\)*(\\"?)?)*("|$))/g
				
				this.syntax[lang]["quotes"]={};
				var quote_tab= [];
				if(this.load_syntax[lang]['QUOTEMARKS']){
					for(var i in this.load_syntax[lang]['QUOTEMARKS']){	
						if(typeof(this.load_syntax[lang]['QUOTEMARKS'][i])=="function") continue;			
						var x=this.get_escaped_regexp(this.load_syntax[lang]['QUOTEMARKS'][i]);
						this.syntax[lang]["quotes"][x]=x;
						//quote_tab[quote_tab.length]="("+x+"(?:\\\\"+x+"|[^"+x+"])*("+x+"|$))";
						//previous working : quote_tab[quote_tab.length]="("+x+"(?:[^"+x+"\\\\]*(\\\\\\\\)*(\\\\"+x+"?)?)*("+x+"|$))";
						quote_tab[quote_tab.length]="("+ x +"(\\\\.|[^"+ x +"])*(?:"+ x +"|$))";
						
						syntax_trace.push(x);			
					}			
				}
						
				this.syntax[lang]["comments"]={};
				if(this.load_syntax[lang]['COMMENT_SINGLE']){
					for(var i in this.load_syntax[lang]['COMMENT_SINGLE']){	
						if(typeof(this.load_syntax[lang]['COMMENT_SINGLE'][i])=="function") continue;						
						var x=this.get_escaped_regexp(this.load_syntax[lang]['COMMENT_SINGLE'][i]);
						quote_tab[quote_tab.length]="("+x+"(.|\\r|\\t)*(\\n|$))";
						syntax_trace.push(x);
						this.syntax[lang]["comments"][x]="\n";
					}			
				}		
				// (/\*(.|[\r\n])*?\*/)
				if(this.load_syntax[lang]['COMMENT_MULTI']){
					for(var i in this.load_syntax[lang]['COMMENT_MULTI']){
						if(typeof(this.load_syntax[lang]['COMMENT_MULTI'][i])=="function") continue;							
						var start=this.get_escaped_regexp(i);
						var end=this.get_escaped_regexp(this.load_syntax[lang]['COMMENT_MULTI'][i]);
						quote_tab[quote_tab.length]="("+start+"(.|\\n|\\r)*?("+end+"|$))";
						syntax_trace.push(start);
						syntax_trace.push(end);
						this.syntax[lang]["comments"][i]=this.load_syntax[lang]['COMMENT_MULTI'][i];
					}			
				}		
				if(quote_tab.length>0)
					this.syntax[lang]["comment_or_quote_reg_exp"]= new RegExp("("+quote_tab.join("|")+")","gi");
				
				if(syntax_trace.length>0) //   /((.|\n)*?)(\\*("|'|\/\*|\*\/|\/\/|$))/g
					this.syntax[lang]["syntax_trace_regexp"]= new RegExp("((.|\n)*?)(\\\\*("+ syntax_trace.join("|") +"|$))", "gmi");
				
				if(this.load_syntax[lang]['SCRIPT_DELIMITERS']){
					this.syntax[lang]["script_delimiters"]= {};
					for(var i in this.load_syntax[lang]['SCRIPT_DELIMITERS']){
						if(typeof(this.load_syntax[lang]['SCRIPT_DELIMITERS'][i])=="function") continue;							
						this.syntax[lang]["script_delimiters"][i]= this.load_syntax[lang]['SCRIPT_DELIMITERS'];
					}			
				}
				
				this.syntax[lang]["custom_regexp"]= {};
				if(this.load_syntax[lang]['REGEXPS']){
					for(var i in this.load_syntax[lang]['REGEXPS']){
						if(typeof(this.load_syntax[lang]['REGEXPS'][i])=="function") continue;
						var val= this.load_syntax[lang]['REGEXPS'][i];
						if(!this.syntax[lang]["custom_regexp"][val['execute']])
							this.syntax[lang]["custom_regexp"][val['execute']]= {};
						this.syntax[lang]["custom_regexp"][val['execute']][i]={'regexp' : new RegExp(val['search'], val['modifiers'])
																			, 'class' : val['class']};
					}
				}
				
				if(this.load_syntax[lang]['STYLES']){							
					lang_style[lang]= {};
					for(var i in this.load_syntax[lang]['STYLES']){
						if(typeof(this.load_syntax[lang]['STYLES'][i])=="function") continue;
						if(typeof(this.load_syntax[lang]['STYLES'][i]) != "string"){
							for(var j in this.load_syntax[lang]['STYLES'][i]){							
								lang_style[lang][j]= this.load_syntax[lang]['STYLES'][i][j];
							}
						}else{
							lang_style[lang][i]= this.load_syntax[lang]['STYLES'][i];
						}
					}
				}
				// build style string
				var style="";		
				for(var i in lang_style[lang]){
					if(lang_style[lang][i].length>0){
						style+= "."+ lang +" ."+ i.toLowerCase() +" span{"+lang_style[lang][i]+"}\n";
						style+= "."+ lang +" ."+ i.toLowerCase() +"{"+lang_style[lang][i]+"}\n";				
					}
				}
				this.syntax[lang]["styles"]=style;
			}
		}				
	};
	
	editAreaLoader.waiting_loading["reg_syntax.js"]= "loaded";
