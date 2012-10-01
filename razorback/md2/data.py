import os
import math
from collections import namedtuple, OrderedDict

import numpy
from pyglet.gl import *

from pygly.shader import Shader
from pygly.texture import Texture
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
        'vert': """
#version 150

// inputs
in vec3 in_position;
in vec2 in_texture_coord;
uniform mat4 model_view;
uniform mat4 projection;

uniform sampler1D verts1;
uniform sampler1D verts2;
uniform sampler1D norms1;
uniform sampler1D norms2;
uniform float fraction;

// outputs
out vec3 ex_normal;
out vec2 ex_texture_coord;

void main()
{
    // extract our vertex position from our textures
    vec4 v1 = vec4( texelFetch( verts1, gl_VertexID, 0 ).xyz, 1.0 );
    vec4 v2 = vec4( texelFetch( verts2, gl_VertexID, 0 ).xyz, 1.0 );
    vec4 n1 = vec4( texelFetch( norms1, gl_VertexID, 0 ).xyz, 1.0 );
    vec4 n2 = vec4( texelFetch( norms2, gl_VertexID, 0 ).xyz, 1.0 );

    // interpolate position
    vec4 v = mix( v1, v2, fraction );
    gl_Position = projection * model_view * v;

    // interpolate normals
    ex_normal = normalize( mix( n1, n2, fraction ) ).xyz;

    // update our texture coordinate
    // we should include a texture matrix here
    ex_texture_coord = in_texture_coord;
}
""",

    'frag': """
#version 150

// inputs
uniform sampler2DRect tex0;
in vec3 ex_normal;
in vec2 ex_texture_coord;

// outputs
out vec4 fragColor;

void main (void)
{
    vec4 colour = texture( tex0, ex_texture_coord.st ) + vec4( 0.1, 0.1, 0.1, 0.0 );
    fragColor = vec4( colour.rgb, 1.0 );
    //fragColor = vec4( 1.0, 1.0, 1.0, 1.0 );
}
"""
    }

    frame_layout = namedtuple(
        'Frame',
        [
            'vertex_texture',
            'normal_texture'
            ]
        )

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

        self.md2 = pymesh.md2.MD2()
        if filename != None:
            self.md2.load( filename )
        else:
            self.md2.load_from_buffer( buffer )

        self._load()

    def __del__( self ):
        vao = getattr( self, vao, None )
        if vao:
            glDeleteVertexArrays( 1, vao )

    def _load( self ):
        """
        Processes the data loaded by the MD2 Loader
        """

        self._load_vertex_buffers()
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
        # convert the frames and store in our dict
        for frame in self.md2.frames:
            # convert our frame data into textures
            vertex_texture = Data.create_1d_texture(
                frame.vertices
                )
            normal_texture = Data.create_1d_texture(
                frame.normals
                )

            # store the frame
            self.frames[ frame.name ] = Data.frame_layout._make(
                [
                    vertex_texture,
                    normal_texture
                    ]
                )

    @staticmethod
    def create_1d_texture( data ):
        # convert data to a  1D texture
        # first convert to a 1D array
        # and then to GLubyte format
        data_view = data.view()
        data_view.shape = (-1,3)

        # create a texture
        texture = Texture( GL_TEXTURE_1D )
        texture.bind()

        # disable texture filtering
        glTexParameteri(
            GL_TEXTURE_1D,
            GL_TEXTURE_MIN_FILTER,
            GL_NEAREST
            )
        glTexParameteri(
            GL_TEXTURE_1D,
            GL_TEXTURE_MAG_FILTER,
            GL_NEAREST
            )
        pygly.texture.set_raw_texture_1d( data_view )

        """
        glTexImage1D(
            GL_TEXTURE_1D,
            0,              # mip level
            GL_RGB32F,      # internal format
            len(gl_data),   # width
            0,              # border
            GL_RGB,         # format
            GL_FLOAT,       # type
            gl_data,        # data
            )
        """

        texture.unbind()

        return texture

    @property
    def num_frames( self ):
        return len( self.frames )

    def render( self, frame, projection, model_view ):
        self.shader.bind()
        self.shader.uniform_matrixf(
            'model_view',
            model_view.flat
            )
        self.shader.uniform_matrixf(
            'projection',
            projection.flat
            )

        # bind our texture indices
        self.shader.uniformi( 'tex0', 0 )
        self.shader.uniformi( 'verts1', 1 )
        self.shader.uniformi( 'norms1', 2 )
        self.shader.uniformi( 'verts2', 3 )
        self.shader.uniformi( 'norms2', 4 )

        # bind the fraction time
        fraction, frame_1 = math.modf( frame )
        frame_2 = (frame_1 + 1.0) % len( self.frames )

        self.shader.uniformf( 'fraction', fraction )

        # get our current frames
        frame_list = self.frames.items()
        frames = (
            frame_list[ int(frame_1) ][ 1 ],
            frame_list[ int(frame_2) ][ 1 ]
            )

        # bind our textures
        # texture 0 is reserved for the model texture
        # this frame
        v1 = frames[ 0 ].vertex_texture
        v2 = frames[ 1 ].vertex_texture
        n1 = frames[ 0 ].normal_texture
        n2 = frames[ 1 ].normal_texture

        # bind the 2 frames
        glActiveTexture( GL_TEXTURE1 )
        v1.bind()
        glActiveTexture( GL_TEXTURE2 )
        n1.bind()
        glActiveTexture( GL_TEXTURE3 )
        v2.bind()
        glActiveTexture( GL_TEXTURE4 )
        n2.bind()

        # we don't bind the diffuse texture
        # this is up to the caller to allow
        # multiple textures to be used per mesh instance

        # unbind the shader
        glBindVertexArray( self.vao )

        glDrawArrays( GL_TRIANGLES, 0, self.num_verts )

        # reset our state
        glBindVertexArray( 0 )
        self.shader.unbind()

        # unbind our textures
        n2.unbind()
        glActiveTexture( GL_TEXTURE3 )
        v2.unbind()
        glActiveTexture( GL_TEXTURE2 )
        n1.unbind()
        glActiveTexture( GL_TEXTURE1 )
        v1.unbind()
        glActiveTexture( GL_TEXTURE0 )

