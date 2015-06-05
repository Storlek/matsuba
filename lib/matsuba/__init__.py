__version__ = '1.6'
__all__ = [
        'Board',
        'acl',
        'adminpanel',
        'config',
        'db',
        'errors',
        'io',
        'mmark',
        'templatetools',
]
__FIOC__ = 'thread over'

# Public board class inherits database methods and IO methods
from matsuba import db, io
class Board(db.Board, io.BoardIO): pass
