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
        
        self.frames = None
        self.vao = None
        self.tc_vbo = None
        self.indice_vbo = None

        self.shader = ShaderProgram(
            False,
            Shader( GL_VERTEX_SHADER, Data.shader_source['vert'] ),
            Shader( GL_FRAGMENT_SHADER, Data.shader_source['frag'] )
            )

        # set our shader data
        # we MUST do this before we link the shader
        self.shader.attributes.in_position_1 = 0
        self.shader.attributes.in_normal_1 = 1
        self.shader.attributes.in_position_2 = 2
        self.shader.attributes.in_normal_2 = 3
        self.shader.attributes.in_texture_coord = 4

        self.shader.frag_location( 'out_frag_colour' )

        # link the shader now
        self.shader.link()

        # bind our uniform indices
        self.shader.bind()
        self.shader.uniforms.in_diffuse = 0
        self.shader.unbind()

        self.md2 = pymesh.md2.MD2()
        if filename != None:
            self.md2.load( filename )
        else:
            self.md2.load_from_buffer( buffer )
        
        # load into OpenGL
        self._load()

    def __del__( self ):
        # free our vao
        vao = getattr( self, 'vao', None )
        if vao:
            glDeleteVertexArrays( 1, vao )

        # free our vbos
        # texture coords
        tcs = getattr( self, 'tc_vbo', None )
        if tcs:
            glDeleteBuffer( tcs )

        # indices
        indices = getattr( self, 'indice_vbo', None )
        if indices:
            glDeleteBuffer( indices )

        # frames
        frames = getattr( self, 'frames', None )
        if frames:
            for frame in frames:
                glDeleteBuffer( frame )

    def _load( self ):
        """
        Prepares the MD2 for rendering by OpenGL.
        """
        def process_vertices( md2 ):
            """Processes MD2 data to generate a single set
            of indices.

            MD2 is an older format that has 2 sets of indices.
            Vertex/Normal indices (md2.triangles.vertex_indices)
            and Texture Coordinate indices (md2.triangles.tc_indices).

            The problem is that modern 3D APIs don't like this.
            OpenGL only allows a single set of indices.

            We can either, extract the vertices, normals and
            texture coordinates using the indices.
            This will create a lot of data.

            This function provides an alternative.
            We iterate through the indices and determine if an index
            has a unique vertex/normal and texture coordinate value.
            If so, the index remains and the texture coordinate is moved
            into the vertex index location in the texture coordinate array.

            If not, a new vertex/normal/texture coordinate value is created
            and the index is updated.

            This function returns a tuple containing the following values.
            (
                [ new indices ],
                [ new texture coordinate array ],
                [ frame_layout( name, vertices, normals ) ]
                )
            """
            # convert our vertex / tc indices to a single indice
            # we iterate through our list and 
            indices = []
            frames = [
                (
                    frame.name,
                    list(frame.vertices),
                    list(frame.normals)
                    )
                for frame in md2.frames
                ]

            # set the size of our texture coordinate list to the
            # same size as one of our frame's vertex lists
            tcs = list( [[None, None]] * len(frames[ 0 ][ 1 ]) )

            for v_index, tc_index in zip(
                md2.triangles.vertex_indices,
                md2.triangles.tc_indices,
                ):

                indice = v_index

                if \
                    tcs[ v_index ][ 0 ] == None and \
                    tcs[ v_index ][ 1 ] == None:
                    # no tc set yet
                    # set ours
                    tcs[ v_index ][ 0 ] = md2.tcs[ tc_index ][ 0 ]
                    tcs[ v_index ][ 1 ] = md2.tcs[ tc_index ][ 1 ]

                elif \
                    tcs[ v_index ][ 0 ] != md2.tcs[ tc_index ][ 0 ] and \
                    tcs[ v_index ][ 1 ] != md2.tcs[ tc_index ][ 1 ]:

                    # a tc has been set and it's not ours
                    # create a new indice
                    indice = len( tcs )

                    # add a new unique vertice
                    for frame in frames:
                        # vertex data
                        frame[ 1 ].append( frame[ 1 ][ v_index ] )
                        # normal data
                        frame[ 2 ].append( frame[ 2 ][ v_index ] )
                    # texture coordinate
                    tcs.append(
                        [
                            md2.tcs[ tc_index ][ 0 ],
                            md2.tcs[ tc_index ][ 1 ]
                            ]
                        )

                # store the index
                indices.append( indice )

            # convert our frames to frame tuples
            frame_tuples = [
                pymesh.md2.MD2.frame_layout(
                    frame[ 0 ],
                    numpy.array( frame[ 1 ], dtype = numpy.float ),
                    numpy.array( frame[ 2 ], dtype = numpy.float )
                    )
                for frame in frames
                ]

            return (
                numpy.array( indices ),
                numpy.array( tcs ),
                frame_tuples
                )


        indices, tcs, frames = process_vertices( self.md2 )

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
        self.tc_vbo = vbos[ 0 ]
        self.indice_vbo = vbos[ 1 ]

        # create our texture coordintes
        tcs = tcs.astype( 'float32' )
        glBindBuffer( GL_ARRAY_BUFFER, self.tc_vbo )
        glBufferData(
            GL_ARRAY_BUFFER,
            tcs.nbytes,
            (GLfloat * tcs.size)(*tcs.flat),
            GL_STATIC_DRAW
            )

        # create our index buffer
        indices = indices.astype( 'uint32' )
        glBindBuffer( GL_ELEMENT_ARRAY_BUFFER, self.indice_vbo )
        glBufferData(
            GL_ELEMENT_ARRAY_BUFFER,
            indices.nbytes,
            (GLuint * indices.size)(*indices.flat),
            GL_STATIC_DRAW
            )

        def create_frame_data( vertices, normals ):
            vbo = (GLuint)()
            glGenBuffers( 1, vbo )

            # interleave these arrays into a single array
            array = numpy.empty( (len(vertices) * 2, 3), dtype = 'float32' )
            array[::2] = vertices
            array[1::2] = normals

            glBindBuffer( GL_ARRAY_BUFFER, vbo )
            glBufferData(
                GL_ARRAY_BUFFER,
                array.nbytes,
                (GLfloat * array.size)(*array.flat),
                GL_STATIC_DRAW
                )

            return vbo

        # convert our frame data into VBOs
        self.frames = [
            create_frame_data( frame.vertices, frame.normals )
            for frame in frames
            ]

        # unbind our buffers
        glBindVertexArray( 0 )
        glBindBuffer( GL_ARRAY_BUFFER, 0 )
        glBindBuffer( GL_ELEMENT_ARRAY_BUFFER, 0 )

    @property
    def num_frames( self ):
        return len( self.md2.frames )

    def render( self, frame1, frame2, interpolation, projection, model_view ):
        # bind our shader and pass in our model view
        self.shader.bind()
        self.shader.uniforms.in_model_view = model_view
        self.shader.uniforms.in_projection = projection
        self.shader.uniforms.in_fraction = interpolation

        # we don't bind the diffuse texture
        # this is up to the caller to allow
        # multiple textures to be used per mesh instance
        frame1_data = self.frames[ frame1 ]
        frame2_data = self.frames[ frame2 ]

        # unbind the shader
        glBindVertexArray( self.vao )

        vertex_size = 6 * 4
        vertex_offset = 0 * 4
        normal_offset = 3 * 4

        # frame 1
        glBindBuffer( GL_ARRAY_BUFFER, frame1_data )
        glEnableVertexAttribArray( 0 )
        glEnableVertexAttribArray( 1 )
        glVertexAttribPointer( 0, 3, GL_FLOAT, GL_FALSE, vertex_size, vertex_offset )
        glVertexAttribPointer( 1, 3, GL_FLOAT, GL_FALSE, vertex_size, normal_offset )

        # frame 2
        glBindBuffer( GL_ARRAY_BUFFER, frame2_data )
        glEnableVertexAttribArray( 2 )
        glEnableVertexAttribArray( 3 )
        glVertexAttribPointer( 2, 3, GL_FLOAT, GL_FALSE, vertex_size, vertex_offset )
        glVertexAttribPointer( 3, 3, GL_FLOAT, GL_FALSE, vertex_size, normal_offset )

        # texture coords
        glBindBuffer( GL_ARRAY_BUFFER, self.tc_vbo )
        glEnableVertexAttribArray( 4 )
        glVertexAttribPointer( 4, 2, GL_FLOAT, GL_FALSE, 0, 0 )

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

