import os
import math

import numpy
from pyglet.gl import *

from pygly.shader import Shader
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
        'frag': open(os.path.dirname(__file__) + '/md2.frag','r').read()
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

        self.shader = Shader(
            vert = Data.shader_source['vert'],
            frag = Data.shader_source['frag']
            )
        self.shader.attribute( 0, 'in_texture_coord' )
        self.shader.frag_location( 'fragColor' )
        self.shader.link()

        # bind our uniform indices
        self.shader.bind()
        self.shader.uniformi( 'tex0', 0 )
        self.shader.uniformi( 'in_vertex_data', 1 )
        self.shader.unbind()

        self.md2 = pymesh.md2.MD2()
        if filename != None:
            self.md2.load( filename )
        else:
            self.md2.load_from_buffer( buffer )
        
        self._load()

    def __del__( self ):
        vao = getattr( self, 'vao', None )
        if vao:
            glDeleteVertexArrays( 1, vao )

    def _load( self ):
        """
        Processes the data loaded by the MD2 Loader
        """
        # convert the md2 data into data for the gpu
        # first, load our vertex buffer objects
        self._load_vertex_buffers()
        # convert our frame data into something we can
        # upload to the gpu
        self._load_frame_data()

    def _load_vertex_buffers( self ):
        # generate a vertex and tc list
        # we can ignore the normals for now
        # as we will pass the normals in per-frame
        self.num_verts = self.md2.frames[ 0 ].vertices.size / 3
        vertices = self.md2.frames[ 0 ].vertices.flatten()
        tcs = self.md2.tcs.flatten()

        # create a vertex array object
        # and vertex buffer objects for our core data
        self.vao = (GLuint)()
        glGenVertexArrays( 1, self.vao )

        # load our buffers
        glBindVertexArray( self.vao )

        # create vertex buffer
        # we only store texture coordinates 
        vbo = (GLuint * 2)()
        glGenBuffers( 2, vbo )

        # create our texture coordinates buffer
        glBindBuffer( GL_ARRAY_BUFFER, vbo[ 1 ] )
        glBufferData(
            GL_ARRAY_BUFFER,
            tcs.nbytes,
            (GLfloat * tcs.size)(*tcs),
            GL_STATIC_DRAW
            )
        glVertexAttribPointer( 0, 2, GL_FLOAT, GL_FALSE, 0, 0)
        glEnableVertexAttribArray( 0 )

        # unbind our buffers
        glBindBuffer( GL_ARRAY_BUFFER, 0 )
        glBindVertexArray( 0 )

    def _load_frame_data( self ):
        def create_texture_array( data ):
            # convert data to a  1D texture
            # first convert to a 1D array
            # and then to GLubyte format

            # create a texture
            texture = Texture2D( GL_TEXTURE_1D_ARRAY )
            texture.bind()

            # disable texture filtering
            texture.set_min_mag_filter(
                min = GL_NEAREST,
                mag = GL_NEAREST
                )

            # shape is num_arrays, width
            # we need it to be width, num_arrays
            # because the glTexImage2D uses
            # the height as the number of textures
            # so change the data shape
            shape = (data.shape[ 1 ], data.shape[ 0 ])
            texture.set_image(
                data.astype('float32').flat,
                shape,
                'f32/rgb/rgb32f'
                )
            texture.unbind()

            return texture

        def extract_frame_data( frame ):
            yield frame.vertices
            yield frame.normals

        # convert our frame data into textures
        # concatenate all our frame data into a single array with
        # the shape:
        # num data arrays x data length x 3
        frames = numpy.array([
            data
            for frame in self.md2.frames
            for data in extract_frame_data( frame )
            ])
        self.frame_textures = create_texture_array( frames )

    @property
    def num_frames( self ):
        return len( self.md2.frames )

    def render( self, frame1, frame2, interpolation, projection, model_view ):
        # bind our shader and pass in our model view
        self.shader.bind()
        self.shader.uniform_matrixf(
            'in_model_view',
            model_view.flat
            )
        self.shader.uniform_matrixf(
            'in_projection',
            projection.flat
            )
        # notify the shader of the blend amount
        self.shader.uniformf( 'in_fraction', interpolation )
        self.shader.uniformi( 'in_frame_1', frame1 )
        self.shader.uniformi( 'in_frame_2', frame2 )

        # bind the vertex data texture
        glActiveTexture( GL_TEXTURE1 )
        self.frame_textures.bind()

        # we don't bind the diffuse texture
        # this is up to the caller to allow
        # multiple textures to be used per mesh instance

        # unbind the shader
        glBindVertexArray( self.vao )

        glDrawArrays( GL_TRIANGLES, 0, self.num_verts )

        # unbind our textures
        self.frame_textures.unbind()
        glActiveTexture( GL_TEXTURE0 )

        # reset our state
        glBindVertexArray( 0 )
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

