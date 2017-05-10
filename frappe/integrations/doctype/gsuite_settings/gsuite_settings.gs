function doGet(e){
  return ContentService.createTextOutput('ok');
}

function doPost(e) {
  var p = JSON.parse(e.postData.contents);

  switch(p.exec){
    case 'new':
      var url = createDoc(p);
      result = { 'url': url };
      break;
    case 'test':
      result = { 'test':'ping'}
  }
  return ContentService.createTextOutput(JSON.stringify(result)).setMimeType(ContentService.MimeType.JSON);
}

function replaceVars(body,p){
  for (key in p) {
    if (p.hasOwnProperty(key)) {
      if (p[key] != null) {
        body.replaceText('{{'+key+'}}', p[key]);
      }
    }
  }
}

function createDoc(p) {
  if(p.destination){
    var folder = DriveApp.getFolderById(p.destination);
  } else {
    var folder = DriveApp.getRootFolder();
  }
  var template = DriveApp.getFileById( p.template )
  var newfile = template.makeCopy( p.filename , folder );

  switch(newfile.getMimeType()){
    case MimeType.GOOGLE_DOCS:
      var body = DocumentApp.openById(newfile.getId()).getBody();
      replaceVars(body,p.vars);
      break;
    case MimeType.GOOGLE_SHEETS:
      //TBD
    case MimeType.GOOGLE_SLIDES:
      //TBD
  }
  return newfile.getUrl()
}
