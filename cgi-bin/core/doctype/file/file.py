class DocType:
  def __init__(self, d, dl):
    self.doc, self.doclist = d,dl

  def validate(self):
    # check for extension
    if not '.' in self.doc.file_name:
      msgprint("Extension required in file name")
      raise Exception

    # set mime type
    if not self.doc.mime_type:
      import mimetypes
      self.doc.mime_type = mimetypes.guess_type(self.doc.file_name)[0] or 'application/unknown'
