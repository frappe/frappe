/**
 * jqPlot
 * Pure JavaScript plotting plugin using jQuery
 *
 * Version: 1.0.0b2_r792
 *
 * Copyright (c) 2009-2011 Chris Leonello
 * jqPlot is currently available for use in all personal or commercial projects 
 * under both the MIT (http://www.opensource.org/licenses/mit-license.php) and GPL 
 * version 2.0 (http://www.gnu.org/licenses/gpl-2.0.html) licenses. This means that you can 
 * choose the license that best suits your project and use it accordingly. 
 *
 * Although not required, the author would appreciate an email letting him 
 * know of any substantial use of jqPlot.  You can reach the author at: 
 * chris at jqplot dot com or see http://www.jqplot.com/info.php .
 *
 * If you are feeling kind and generous, consider supporting the project by
 * making a donation at: http://www.jqplot.com/donate.php .
 *
 * sprintf functions contained in jqplot.sprintf.js by Ash Searle:
 *
 *     version 2007.04.27
 *     author Ash Searle
 *     http://hexmen.com/blog/2007/03/printf-sprintf/
 *     http://hexmen.com/js/sprintf.js
 *     The author (Ash Searle) has placed this code in the public domain:
 *     "This code is unrestricted: you are free to use it however you like."
 * 
 */
(function(b){b.jqplot.EnhancedLegendRenderer=function(){b.jqplot.TableLegendRenderer.call(this)};b.jqplot.EnhancedLegendRenderer.prototype=new b.jqplot.TableLegendRenderer();b.jqplot.EnhancedLegendRenderer.prototype.constructor=b.jqplot.EnhancedLegendRenderer;b.jqplot.EnhancedLegendRenderer.prototype.init=function(c){this.numberRows=null;this.numberColumns=null;this.seriesToggle="normal";this.disableIEFading=true;b.extend(true,this,c);if(this.seriesToggle){b.jqplot.postDrawHooks.push(a)}};b.jqplot.EnhancedLegendRenderer.prototype.draw=function(){var e=this;if(this.show){var n=this._series;var o;var q="position:absolute;";q+=(this.background)?"background:"+this.background+";":"";q+=(this.border)?"border:"+this.border+";":"";q+=(this.fontSize)?"font-size:"+this.fontSize+";":"";q+=(this.fontFamily)?"font-family:"+this.fontFamily+";":"";q+=(this.textColor)?"color:"+this.textColor+";":"";q+=(this.marginTop!=null)?"margin-top:"+this.marginTop+";":"";q+=(this.marginBottom!=null)?"margin-bottom:"+this.marginBottom+";":"";q+=(this.marginLeft!=null)?"margin-left:"+this.marginLeft+";":"";q+=(this.marginRight!=null)?"margin-right:"+this.marginRight+";":"";this._elem=b('<table class="jqplot-table-legend" style="'+q+'"></table>');if(this.seriesToggle){this._elem.css("z-index","3")}var w=false,m=false,c,k;if(this.numberRows){c=this.numberRows;if(!this.numberColumns){k=Math.ceil(n.length/c)}else{k=this.numberColumns}}else{if(this.numberColumns){k=this.numberColumns;c=Math.ceil(n.length/this.numberColumns)}else{c=n.length;k=1}}var v,t,d,g,f,h,l;var p=0;for(v=n.length-1;v>=0;v--){if(n[v]._stack||n[v].renderer.constructor==b.jqplot.BezierCurveRenderer){m=true}}for(v=0;v<c;v++){if(m){d=b('<tr class="jqplot-table-legend"></tr>').prependTo(this._elem)}else{d=b('<tr class="jqplot-table-legend"></tr>').appendTo(this._elem)}for(t=0;t<k;t++){if(p<n.length&&n[p].show&&n[p].showLabel){o=n[p];h=this.labels[p]||o.label.toString();if(h){var r=o.color;if(!m){if(v>0){w=true}else{w=false}}else{if(v==c-1){w=false}else{w=true}}l=(w)?this.rowSpacing:"0";g=b('<td class="jqplot-table-legend" style="text-align:center;padding-top:'+l+';"><div><div class="jqplot-table-legend-swatch" style="background-color:'+r+";border-color:"+r+';"></div></div></td>');f=b('<td class="jqplot-table-legend" style="padding-top:'+l+';"></td>');if(this.escapeHtml){f.text(h)}else{f.html(h)}if(m){if(this.showLabels){f.prependTo(d)}if(this.showSwatches){g.prependTo(d)}}else{if(this.showSwatches){g.appendTo(d)}if(this.showLabels){f.appendTo(d)}}if(this.seriesToggle){var u;if(typeof(this.seriesToggle)=="string"||typeof(this.seriesToggle)=="number"){if(!b.jqplot.use_excanvas||!this.disableIEFading){u=this.seriesToggle}}if(this.showSwatches){g.bind("click",{series:o,speed:u},o.toggleDisplay);g.addClass("jqplot-seriesToggle")}if(this.showLabels){f.bind("click",{series:o,speed:u},o.toggleDisplay);f.addClass("jqplot-seriesToggle")}}w=true}}p++}}}return this._elem};var a=function(){if(this.legend.renderer.constructor==b.jqplot.EnhancedLegendRenderer&&this.legend.seriesToggle){var c=this.legend._elem.detach();this.eventCanvas._elem.after(c)}}})(jQuery);