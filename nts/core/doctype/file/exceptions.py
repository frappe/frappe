import nts


class MaxFileSizeReachedError(nts.ValidationError):
	pass


class FolderNotEmpty(nts.ValidationError):
	pass


class FileTypeNotAllowed(nts.ValidationError):
	pass


from nts.exceptions import *
