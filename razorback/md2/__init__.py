"""
Improve using tips from here
http://developer.apple.com/library/ios/#documentation/3DDrawing/Conceptual/OpenGLES_ProgrammingGuide/TechniquesforWorkingwithVertexData/TechniquesforWorkingwithVertexData.html

* move frame data out of texture and back into vertex attributes
* interleave vertex data
* convert tu / tv to GL_SHORT / GL_UNSIGNED_SHORT
"""

import os
import math

import numpy
from pyglet.gl import *

from pygly.shader import Shader, ShaderProgram
from pygly.texture import Texture2D
import pygly.texture
import pymesh.md2

from razorback.keyframe_mesh import KeyframeMesh


class Data( object ):
    """
    Provides the ability to load and render an MD2
    mesh.

    Uses MD2 to load MD2 mesh data.
    Loads mesh data onto the graphics card to speed
    up rendering. Allows for pre-baking the interpolation
    of frames.
    """

    shader_source = {
        'vert': open(os.path.dirname(__file__) + '/md2.vert','r').read(),
        'frag': open(os.path.dirname(__file__) + '/md2.frag','r').read(),
    }

    _data = {}

    @classmethod 
    def load( cls, filename ): 
        # check if the model has been loaded previously 
        if filename in Data._data: 
            # create a new mesh with the same data 
            return Data._data[ filename ]

        data = cls( filename ) 

        # store mesh for later 
        Data._data[ filename ] = data

        return data

    @classmethod
    def unload( cls, filename ):
        if filename in Data._data:
            del Data._data[ filename ]

    def __init__( self, filename = None, buffer = None ):
        """
        Loads an MD2 from the specified file.

        @param filename: the filename to load the mesh from.
        @param interpolation: the number of frames to generate
        between each loaded frame.
        0 is the default (no interpolation).
        It is suggested to keep the value low (0-2) to avoid
        long load times.
        """
        super( Data, self ).__init__()
        
        self.frame_textures = None
        self.vertex_list = None

        self.shader = ShaderProgram(
            False,
            Shader( GL_VERTEX_SHADER, Data.shader_source['vert'] ),
            Shader( GL_FRAGMENT_SHADER, Data.shader_source['frag'] )
            )

        # set our shader data
        # we MUST do this before we link the shader
        self.shader.attribute( 0, 'in_position_1' )
        self.shader.attribute( 1, 'in_normal_1' )
        self.shader.attribute( 2, 'in_position_2' )
        self.shader.attribute( 3, 'in_normal_2' )
        self.shader.attribute( 4, 'in_texture_coord' )
        self.shader.frag_location( 'out_frag_colour' )

        # link the shader now
        self.shader.link()

        # bind our uniform indices
        self.shader.bind()
        self.shader.uniformi( 'tex0', 0 )
        self.shader.unbind()

        self.md2 = pymesh.md2.MD2()
        if filename != None:
            self.md2.load( filename )
        else:
            self.md2.load_from_buffer( buffer )
        
        # load into OpenGL
        self._load()

    def __del__( self ):
        vao = getattr( self, 'vao', None )
        if vao:
            glDeleteVertexArrays( 1, vao )
        # TODO: free our frame vbos

    def _load( self ):
        """
        Prepares the MD2 for rendering by OpenGL.
        """
        indices, tcs, frames = pymesh.md2.MD2.process_vertices( self.md2 )

        self.num_indices = len( indices )

        # create a vertex array object
        # and vertex buffer objects for our core data
        self.vao = (GLuint)()
        glGenVertexArrays( 1, self.vao )

        # load our buffers
        glBindVertexArray( self.vao )

        # create our vbo buffers
        # one for texture coordinates
        # one for indices
        vbos = (GLuint * 2)()
        glGenBuffers( len(vbos), vbos )

        # create our texture coordintes
        self.tc_vbo = vbos[ 0 ]
        tcs = tcs.astype( 'float32' )
        glBindBuffer( GL_ARRAY_BUFFER, self.tc_vbo )
        glBufferData(
            GL_ARRAY_BUFFER,
            tcs.nbytes,
            (GLfloat * tcs.size)(*tcs.flat),
            GL_STATIC_DRAW
            )

        # create our index buffer
        self.indice_vbo = vbos[ 1 ]
        indices = indices.astype( 'uint32' )
        glBindBuffer( GL_ELEMENT_ARRAY_BUFFER, self.indice_vbo )
        glBufferData(
            GL_ELEMENT_ARRAY_BUFFER,
            indices.nbytes,
            (GLuint * indices.size)(*indices.flat),
            GL_STATIC_DRAW
            )

        # unbind our buffers
        glBindVertexArray( 0 )
        glBindBuffer( GL_ARRAY_BUFFER, 0 )
        glBindBuffer( GL_ELEMENT_ARRAY_BUFFER, 0 )

        def create_frame_data( vertices, normals ):
            vbos = (GLuint * 2)()
            glGenBuffers( 2, vbos )

            # TODO: interleave these arrays

            vertices = vertices.astype( 'float32' )
            glBindBuffer( GL_ARRAY_BUFFER, vbos[ 0 ] )
            glBufferData(
                GL_ARRAY_BUFFER,
                vertices.nbytes,
                (GLfloat * vertices.size)(*vertices.flat),
                GL_STATIC_DRAW
                )

            normals = normals.astype( 'float32' )
            glBindBuffer( GL_ARRAY_BUFFER, vbos[ 1 ] )
            glBufferData(
                GL_ARRAY_BUFFER,
                normals.nbytes,
                (GLfloat * normals.size)(*normals.flat),
                GL_STATIC_DRAW
                )

            return tuple(vbos)

        # convert our frame data into textures
        # concatenate all our frame data into a single array with
        # the shape:
        # num data arrays x data length x 3
        self.frames = [
            create_frame_data( frame.vertices, frame.normals )
            for frame in frames
            ]

        # unbind any buffers
        glBindBuffer( GL_ARRAY_BUFFER, 0 )

    @property
    def num_frames( self ):
        return len( self.md2.frames )

    def render( self, frame1, frame2, interpolation, projection, model_view ):
        # bind our shader and pass in our model view
        self.shader.bind()
        self.shader.uniform_matrixf( 'in_model_view', model_view.flat )
        self.shader.uniform_matrixf( 'in_projection', projection.flat )
        self.shader.uniformf( 'in_fraction', interpolation )

        # we don't bind the diffuse texture
        # this is up to the caller to allow
        # multiple textures to be used per mesh instance
        frame1_data = self.frames[ frame1 ]
        frame2_data = self.frames[ frame2 ]
        v1, v2 = frame1_data[ 0 ], frame2_data[ 0 ]
        n1, n2 = frame1_data[ 1 ], frame2_data[ 1 ]

        # unbind the shader
        glBindVertexArray( self.vao )

        # frame 1
        glBindBuffer( GL_ARRAY_BUFFER, v1 )
        glVertexAttribPointer( 0, 3, GL_FLOAT, GL_FALSE, 0, 0 )
        glEnableVertexAttribArray( 0 )
        glBindBuffer( GL_ARRAY_BUFFER, n1 )
        glVertexAttribPointer( 1, 3, GL_FLOAT, GL_FALSE, 0, 0 )
        glEnableVertexAttribArray( 1 )

        # frame 2
        glBindBuffer( GL_ARRAY_BUFFER, v2 )
        glVertexAttribPointer( 2, 3, GL_FLOAT, GL_FALSE, 0, 0 )
        glEnableVertexAttribArray( 2 )
        glBindBuffer( GL_ARRAY_BUFFER, n2 )
        glVertexAttribPointer( 3, 3, GL_FLOAT, GL_FALSE, 0, 0 )
        glEnableVertexAttribArray( 3 )

        # texture coords
        glBindBuffer( GL_ARRAY_BUFFER, self.tc_vbo )
        glVertexAttribPointer( 4, 2, GL_FLOAT, GL_FALSE, 0, 0 )
        glEnableVertexAttribArray( 4 )

        # indices
        glBindBuffer( GL_ELEMENT_ARRAY_BUFFER, self.indice_vbo )

        glDrawElements(
            GL_TRIANGLES,
            self.num_indices,
            GL_UNSIGNED_INT,
            0
            )

        # reset our state
        glBindVertexArray( 0 )
        glBindBuffer( GL_ELEMENT_ARRAY_BUFFER, 0 )
        glBindBuffer( GL_ARRAY_BUFFER, 0 )
        self.shader.unbind()


class MD2_Mesh( KeyframeMesh ):
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
        """
        super( MD2_Mesh, self ).__init__()
        
        self.filename = filename
        self.data = None
        self.frame_1 = 0
        self.frame_2 = 0
        self.interpolation = 0.0

    @property
    def num_frames( self ):
        """Returns the number of keyframes.
        """
        return self.data.num_frames

    @property
    def animations( self ):
        """Returns the frame namesfor various animations.
        """
        return pymesh.md2.MD2.animations.keys()

    @property
    def animation( self ):
        """Returns the name of the current animation.

        This is determined by the current frame number.
        The animation name is taken from the standard MD2
        animation names and not from the MD2 file itself.
        """
        for name, value in pymesh.md2.MD2.animations.items():
            if \
                value[ 0 ] <= self.frame_1 and \
                value[ 1 ] >= self.frame_1:
                return name
        # unknown animation
        return None

    @property
    def frame_name( self ):
        return self.data.md2.frames[ self.frame_1 ].name

    @property
    def frame_rate( self ):
        """Returns the frames per second for the current animation.

        This uses the standard MD2 frame rate definition
        If the frame rate differs, over-ride this function.
        If the animation is outside the range of standard
        animations, a default value of 7.0 is returned.
        """
        anim = self.animation
        if anim:
            return self.animation_frame_rate( self.animation )
        else:
            return 7.0

    def animation_start_end_frame( self, animation ):
        return (
            pymesh.md2.MD2.animations[ animation ][ 0 ],
            pymesh.md2.MD2.animations[ animation ][ 1 ]
            )

    def animation_frame_rate( self, animation ):
        """Returns the frame rate for the specified animation
        """
        return pymesh.md2.MD2.animations[ animation ][ 2 ]

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
        self.data.render(
            self.frame_1,
            self.frame_2,
            self.interpolation,
            projection,
            model_view
            )

