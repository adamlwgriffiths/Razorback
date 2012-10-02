import os
import math
from collections import namedtuple, OrderedDict

import numpy
from pyglet.gl import *

from pygly.shader import Shader
from pygly.texture import Texture2D
import pygly.texture

import pymesh.md2


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
        
        # remember the order frames are added
        self.frames = OrderedDict([])
        self.vertex_list = None
        self.shader = Shader(
            vert = Data.shader_source['vert'],
            frag = Data.shader_source['frag']
            )
        self.shader.attribute( 0, 'in_position' )
        self.shader.attribute( 1, 'in_texture_coord' )
        self.shader.frag_location( 'fragColor' )
        self.shader.link()

        # bind our uniform indices
        self.shader.bind()
        self.shader.uniformi( 'tex0', 0 )
        self.shader.uniformi( 'verts1', 1 )
        self.shader.uniformi( 'verts2', 2 )
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

        # create 2 vertex buffers
        # 0 is position
        # 1 is texture coordinates 
        vbo = (GLuint * 2)()
        glGenBuffers( 2, vbo )

        # load our buffers
        glBindVertexArray( self.vao )

        # create our vertex position buffer
        glBindBuffer( GL_ARRAY_BUFFER, vbo[ 0 ] )
        glBufferData(
            GL_ARRAY_BUFFER,
            vertices.nbytes,
            (GLfloat * vertices.size)(*vertices),
            GL_STATIC_DRAW
            )
        glVertexAttribPointer( 0, 3, GL_FLOAT, GL_FALSE, 0, 0)
        glEnableVertexAttribArray( 0 )

        # create our texture coordinates buffer
        glBindBuffer( GL_ARRAY_BUFFER, vbo[ 1 ] )
        glBufferData(
            GL_ARRAY_BUFFER,
            tcs.nbytes,
            (GLfloat * tcs.size)(*tcs),
            GL_STATIC_DRAW
            )
        glVertexAttribPointer( 1, 2, GL_FLOAT, GL_FALSE, 0, 0)
        glEnableVertexAttribArray( 1 )

        # unbind our buffers
        glBindVertexArray( 0 )

    def _load_frame_data( self ):
        def create_texture_array( *data ):
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

            all_data = numpy.array( data )

            # shape is num, width, channels
            # we need it to be width, num, channels
            # because the height (glTexImage2D) uses
            # the height as the number of textures
            # so change the data shape
            shape = (all_data.shape[ 1 ], all_data.shape[ 0 ])
            texture.set_image(
                all_data.astype('float32').flat,
                shape,
                'f32/rgb/rgb32f'
                )
            texture.unbind()

            return texture

        # convert the frames and store in our dict
        for frame in self.md2.frames:
            # convert our frame data into textures
            self.frames[ frame.name ] = create_texture_array(
                frame.vertices,
                frame.normals
                )

    @property
    def num_frames( self ):
        return len( self.frames )

    def render( self, frame, projection, model_view ):
        # calculate the current and next frame
        # and the blending fraction
        fraction, frame_1 = math.modf( frame )
        frame_2 = (frame_1 + 1.0) % len( self.frames )

        # bind our shader and pass in our model view
        self.shader.bind()
        self.shader.uniform_matrixf(
            'model_view',
            model_view.flat
            )
        self.shader.uniform_matrixf(
            'projection',
            projection.flat
            )
        # notify the shader of the blend amount
        self.shader.uniformf( 'fraction', fraction )

        # get our current frames
        # convert our ordered dict from key:value to
        # the order of frames
        frame_list = self.frames.items()

        # bind our textures
        # texture 0 is reserved for the model texture
        # this frame
        v1 = frame_list[ int(frame_1) ][ 1 ]
        v2 = frame_list[ int(frame_2) ][ 1 ]

        # bind the 2 frames
        glActiveTexture( GL_TEXTURE1 )
        v1.bind()
        glActiveTexture( GL_TEXTURE2 )
        v2.bind()

        # we don't bind the diffuse texture
        # this is up to the caller to allow
        # multiple textures to be used per mesh instance

        # unbind the shader
        glBindVertexArray( self.vao )

        glDrawArrays( GL_TRIANGLES, 0, self.num_verts )

        # unbind our textures
        v2.unbind()
        glActiveTexture( GL_TEXTURE1 )
        v1.unbind()
        glActiveTexture( GL_TEXTURE0 )

        # reset our state
        glBindVertexArray( 0 )
        self.shader.unbind()

