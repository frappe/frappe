export default class LinkStore{
    from_name = ""
    from_doctype = ""
    to_doctype = ""
   constructor(){}

   setFromName(name){
    console.log("enter");
       this.from_name = name
   }
   setFromDoctype(doctype){
       this.from_doctype = doctype 
   }
   setToDoctype(doctype){
    this.to_doctype = doctype 
}
   getFromName(){
       return this.from_name
   }
   getFromDoctype(){
       return this.from_doctype
   }
   getToDoctype(){
    return this.to_doctype
}
}