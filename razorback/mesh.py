

class Mesh( object ):

    def __init__( self ):
        super( Mesh, self ).__init__()

    def __enter__( self ):
        self.bind()

    def __exit__( self, exc_type, exc_value, traceback ):
        self.unbind()

    def bind( self ):
        pass

    def unbind( self ):
        pass

