# -*- coding: utf-8 -*-
"""
Created on 02/04/2012

@author: adam
"""

from pygly.shader import Shader
from pygly.gl import *

from razorback.keyframe_mesh import KeyframeMesh
from razorback.md2.data import Data


class MD2( KeyframeMesh ):
    """
    Provides the ability to load and render an MD2
    mesh.

    Uses MD2 to load MD2 mesh data.
    Loads mesh data onto the graphics card to speed
    up rendering. Allows for pre-baking the interpolation
    of frames.
    """
    
    def __init__( self, filename ):
        """
        Loads an MD2 from the specified file.

        @param data: The MD2_Data object.
        This is seperated from the MD2 mesh so that
        you can have multiple meshes with a single
        data source. That way you don't have to load
        and store an MD2 multiple times.
        """
        super( MD2, self ).__init__()
        
        self.filename = filename
        self.frame = 0.0
        self.data = None

    @property
    def num_frames( self ):
        return self.data.num_frames

    def load( self ):
        """
        Reads the MD2 data from the existing
        specified filename.
        """
        if self.data == None:
            self.data = Data.load( self.filename )

    def unload( self ):
        if self.data != None:
            self.data = None
            Data.unload( self.filename )

    def render( self, projection, model_view ):
        # TODO: bind our diffuse texture to TEX0
        self.data.render( self.frame, projection, model_view )

