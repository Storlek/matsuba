class MatsubaError(Exception):
        status = "500 Internal Server Error"
        header = "wat"
        # from apache
        message = "The server encountered an internal error and was unable to complete your request."

class NotFoundError(MatsubaError):
        status = "404 Not Found"
        header = "Not Found"
        message = "Whatever you're looking for, it's not here."
class BoardNotFoundError(NotFoundError):
        header = "Board Not Found"
class PostNotFoundError(NotFoundError):
        header = "Post Not Found"

class NoPermissionError(MatsubaError):
        status = "403 Forbidden"
        header = "Permission Denied"
        message = "I'm sorry, Dave, I can't let you do that."
class FloodError(NoPermissionError):
        header = "Flood Detected"
        message = "If it was really important, wait a while and try again."
class SpamError(NoPermissionError):
        header = "Spam Trap Activated"
        message = "Your post got eaten by the spam filter. OM NOM NOM NOM."
class BannedError(NoPermissionError):
        header = "You Are Banned"
        message = "Now run along and go play outside."

class PostDataError(NoPermissionError):
        status = "400 Bad Request"
        header = "Improper Post Data"
        message = "lol hax"
class MessageLengthError(PostDataError):
        header = "Message Too Long"
class EmptyPostError(PostDataError):
        header = "Empty Post"
        message = "Your post lacks content."

class MethodNotAllowedError(PostDataError):
        status = "405 Method Not Allowed"
        header = "Method Not Allowed"

class FileTypeError(NoPermissionError):
        status = "415 Unsupported Media Type"
        header = "File Not Permitted"
        message = "You can't post that here."

class DuplicateError(FileTypeError):
        status = "409 Conflict"
        header = "File Already Posted"
        message = "lol flood"
