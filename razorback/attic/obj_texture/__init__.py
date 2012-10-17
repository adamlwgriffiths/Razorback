import os
from collections import OrderedDict

import numpy
import numpy.ma
from pyglet.gl import *

from pygly.shader import Shader
from pygly.texture import Texture2D
import pygly.texture
import pymesh.obj

from razorback.mesh import Mesh


class Data( object ):

    shader_source = {
        'vert': open(os.path.dirname(__file__) + '/obj.vert','r').read(),
        'frag': open(os.path.dirname(__file__) + '/obj.frag','r').read()
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
        super( Data, self ).__init__()

        self.meshes = {}

        # create our shader
        self.shader = Shader(
            vert = Data.shader_source['vert'],
            frag = Data.shader_source['frag']
            )

        self.shader.attribute( 0, 'in_position_index' )
        self.shader.attribute( 1, 'in_texture_coord_index' )
        self.shader.attribute( 2, 'in_normal_index' )
        self.shader.frag_location( 'fragColor' )
        self.shader.link()

        # bind our uniform indices
        self.shader.bind()
        self.shader.uniformi( 'tex0', 0 )
        self.shader.uniformi( 'in_positions', 1 )
        self.shader.uniformi( 'in_texture_coords', 2 )
        self.shader.uniformi( 'in_normals', 3 )
        self.shader.unbind()

        self.meshes = {}
        self.vertex_texture = None
        self.texture_coord_texture = None
        self.normal_texture = None

        self.obj = pymesh.obj.OBJ()
        if filename != None:
            self.obj.load( filename )
        else:
            self.obj.load_from_buffer( buffer )
        
        self._load()

    def _load( self ):
        """
        Processes the data loaded by the MD2 Loader
        """
        # convert the md2 data into data for the gpu
        # first, load our vertex buffer objects
        self._load_vertex_buffers()

    def _load_vertex_buffers( self ):
        # create a Vertex Array Object
        # these are required to do any rendering
        self.vao = (GLuint)()
        glGenVertexArrays( 1, self.vao )
        glBindVertexArray( self.vao )

        # convert to numpy for easy manipulation
        vertices = numpy.array( self.obj.model.vertices, dtype = 'float32' )
        texture_coords = numpy.array( self.obj.model.texture_coords, dtype = 'float32' )
        normals = numpy.array( self.obj.model.normals, dtype = 'float32' )

        # ensure our vertices fit within our max texture width
        max_width = GLint()
        glGetIntegerv( GL_MAX_TEXTURE_SIZE, max_width )
        max_width = max_width.value

        def resize_array( array, max_width ):
            if array.shape[ 0 ] > max_width:
                num_arrays = int(array.shape[ 0 ] / max_width) + 1
                array = numpy.resize( array, (num_arrays, max_width, array.shape[ 1 ]) )
            else:
                array.shape = (1, array.shape[ 0 ], array.shape[ 1 ])
            print array.shape, max_width
            return array

        vertices = resize_array( vertices, max_width )
        if texture_coords.size > 0:
            texture_coords = resize_array( texture_coords, max_width )
        if normals.size > 0:
            normals = resize_array( normals, max_width )

        # convert to Texture1D
        def create_texture( data, format ):
            # convert data to a  1D texture
            # first convert to a 1D array
            # and then to GLubyte format

            # create a texture
            texture = Texture2D( GL_TEXTURE_1D_ARRAY )
            texture.bind()

            # disable texture filtering
            texture.set_min_mag_filter( min = GL_NEAREST, mag = GL_NEAREST )

            # set the texture data
            texture.set_image(
                data.astype('float32').flat,
                [data.shape[ 1 ], data.shape[ 0 ]],
                format
                )

            texture.unbind()

            return texture

        self.vertex_texture = create_texture(
            vertices,
            'f32/rgb/rgb32f'
            )
        if texture_coords.size > 0:
            self.texture_coord_texture = create_texture(
                texture_coords,
                'f32/rg/rg32f'
                )
        if normals.size > 0:
            self.normal_texture = create_texture(
                normals,
                'f32/rgb/rgb32f'
                )

        # convert each meshes' indices into attribute arrays
        # iterate through each mesh group
        for mesh in self.obj.model.meshes:
        #for mesh in self.obj.model.meshes.itervalues():
            print 'Name:', mesh[ 'name' ], 'Groups:', mesh[ 'groups' ]

            # points
            points = numpy.array( mesh['points'] )

            num_point_indices = len(points)
            if num_point_indices:
                # replace None with invalid values
                points = numpy.ma.masked_values( points, None ).filled( -1 )

                points_v = points[ :, 0 ]
                points_t = points[ :, 1 ]
                points_n = points[ :, 2 ]

            # lines
            # convert from line strips to line segments
            def convert_to_lines( strip ):
                previous = strip[ 0 ]
                for point in strip[ 1: ]:
                    yield previous
                    yield point
                    previous = point
            
            # convert each line strip into line segments
            lines = numpy.array([
                value
                for strip in mesh['lines']
                for value in convert_to_lines( strip )
                ])

            num_line_indices = len(lines)
            if num_line_indices:
                # replace None with invalid values
                lines = numpy.ma.masked_values( lines, None ).filled( -1 )

                lines_v = lines[ :, 0 ]
                lines_t = lines[ :, 1 ]
                lines_n = lines[ :, 2 ]

            # faces
            # convert from triangle fans to triangles
            def convert_to_triangles( fan ):
                # convert from triangle fan
                # 0, 1, 2, 3, 4, 5
                # to triangle list
                # 0, 1, 2, 0, 2, 3, 0, 3, 4, 0, 4, 5
                start = fan[ 0 ]
                previous = fan[ 1 ]
                for point in fan[ 2: ]:
                    yield start
                    yield previous
                    yield point
                    previous = point

            # convert each triangle face to triangles
            triangles = numpy.array([
                value
                for triangle in mesh['faces']
                for value in convert_to_triangles( triangle )
                ])

            num_triangle_indices = len(triangles)
            if num_triangle_indices:
                # replace None with invalid values
                triangles = numpy.ma.masked_values( triangles, None ).filled( -1 )

                triangles_v = triangles[ :, 0 ]
                triangles_t = triangles[ :, 1 ]
                triangles_n = triangles[ :, 2 ]

            v = []
            t = []
            n = []
            if num_point_indices:
                v.append( points_v )
                t.append( points_t )
                n.append( points_n )
            if num_line_indices:
                v.append( lines_v )
                t.append( lines_t )
                n.append( lines_n )
            if num_triangle_indices:
                v.append( triangles_v )
                t.append( triangles_t )
                n.append( triangles_n )

            v_indices = numpy.hstack( tuple( v ) ).astype( 'int32' )
            t_indices = numpy.hstack( tuple( t ) ).astype( 'int32' )
            n_indices = numpy.hstack( tuple( n ) ).astype( 'int32' )

            # create our global vertex data
            mesh_vbos = (GLuint * 3)()
            glGenBuffers( 3, mesh_vbos )

            # create ours VBOs to store our indices
            # TODO: store these in 1 buffer using stride
            # http://www.opengl.org/sdk/docs/man3/xhtml/glVertexAttribPointer.xml

            # vertices
            glBindBuffer( GL_ARRAY_BUFFER, mesh_vbos[ 0 ] )
            glBufferData(
                GL_ARRAY_BUFFER,
                v_indices.nbytes,
                (GLint * v_indices.size)(*v_indices),
                GL_STATIC_DRAW
                )

            # texture coords
            glBindBuffer( GL_ARRAY_BUFFER, mesh_vbos[ 1 ] )
            glBufferData(
                GL_ARRAY_BUFFER,
                t_indices.nbytes,
                (GLint * t_indices.size)(*t_indices),
                GL_STATIC_DRAW
                )
            
            # normals
            glBindBuffer( GL_ARRAY_BUFFER, mesh_vbos[ 2 ] )
            glBufferData(
                GL_ARRAY_BUFFER,
                n_indices.nbytes,
                (GLint * n_indices.size)(*n_indices),
                GL_STATIC_DRAW
                )

            # store our indices
            gl_data = (
                mesh_vbos,
                (0, num_point_indices),
                (num_point_indices, num_line_indices),
                (num_point_indices + num_line_indices, num_triangle_indices)
                )

            # add the mesh to each of the mesh groups
            # each group has a list of meshes it owns
            for group in mesh['groups']:
                if group not in self.meshes:
                    self.meshes[ group ] = []
                self.meshes[ group ].append( gl_data )

        # unbind our arrays
        glBindBuffer( GL_ARRAY_BUFFER, 0 )
        glBindVertexArray( 0 )

    def render( self, projection, model_view, groups ):
        self.shader.bind()
        self.shader.uniform_matrixf( 'model_view', model_view.flat )
        self.shader.uniform_matrixf( 'projection', projection.flat )

        glBindVertexArray( self.vao )

        # bind our global data
        # vertices
        glActiveTexture( GL_TEXTURE1 )
        self.vertex_texture.bind()

        # texture coordinates
        if self.texture_coord_texture:
            glActiveTexture( GL_TEXTURE2 )
            self.texture_coord_texture.bind()

        # normals
        if self.normal_texture:
            glActiveTexture( GL_TEXTURE3 )
            self.normal_texture.bind()

        # render each set of indices
        glEnableVertexAttribArray( 0 )
        glEnableVertexAttribArray( 1 )
        glEnableVertexAttribArray( 2 )

        # iterate through the specified groups
        for group in groups:
            # get the group
            for mesh in self.meshes[ group ]:
                mesh_vbo, points, lines, triangles = mesh
                v_indices, t_indices, n_indices = mesh_vbo

                # vertex indices
                glBindBuffer( GL_ARRAY_BUFFER, v_indices )
                glVertexAttribIPointer( 0, 1, GL_INT, GL_FALSE, 0, 0 )

                # texture coordinate indices
                glBindBuffer( GL_ARRAY_BUFFER, t_indices )
                glVertexAttribIPointer( 1, 1, GL_INT, GL_FALSE, 0, 0 )

                # normal indices
                glBindBuffer( GL_ARRAY_BUFFER, n_indices )
                glVertexAttribIPointer( 2, 1, GL_INT, GL_FALSE, 0, 0 )

                # render the group
                if points[ 1 ] > 0:
                    start, count = 0, points[ 1 ]
                    glDrawArrays( GL_POINTS, start, count )
                if lines[ 1 ] > 0:
                    start, count = points[ 1 ], lines[ 1 ]
                    glDrawArrays( GL_LINES, start, count )
                if triangles[ 1 ] > 0:
                    start, count = points[ 1 ] + lines[ 1 ], triangles[ 1 ]
                    glDrawArrays( GL_TRIANGLES, start, count )

        # cleanup
        glDisableVertexAttribArray( 0 )
        glDisableVertexAttribArray( 1 )
        glDisableVertexAttribArray( 2 )

        # unbind our textures
        if self.normal_texture:
            self.normal_texture.unbind()
        if self.texture_coord_texture:
            glActiveTexture( GL_TEXTURE2 )
            self.texture_coord_texture.unbind()
        glActiveTexture( GL_TEXTURE1 )
        self.vertex_texture.unbind()
        glActiveTexture( GL_TEXTURE0 )

        # unbind our buffers
        glBindBuffer( GL_ARRAY_BUFFER, 0 )
        glBindBuffer( GL_ELEMENT_ARRAY_BUFFER, 0 )
        glBindVertexArray( 0 )

        self.shader.unbind()




class OBJ_Mesh( Mesh ):
    def __init__( self, filename ):
        """
        Loads an OBJ from the specified file.
        """
        super( OBJ_Mesh, self ).__init__()
        
        self.filename = filename
        self.data = None

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

    def render( self, projection, model_view, groups ):
        self.data.render(
            projection,
            model_view,
            groups
            )

