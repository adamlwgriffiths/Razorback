import os
from collections import OrderedDict

from pyglet.gl import *

from pygly.shader import Shader, ShaderProgram
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
        self.shader = ShaderProgram(
            Shader( GL_VERTEX_SHADER, Data.shader_source['vert'] ),
            Shader( GL_FRAGMENT_SHADER, Data.shader_source['frag'] ),
            link_now = False
            )

        # set our shader data
        # we MUST do this before we link the shader
        self.shader.attributes.in_position = 0
        self.shader.attributes.in_texture_coord = 1
        self.shader.attributes.in_normal = 2
        self.shader.frag_location( 'out_frag_colour' )

        # link the shader now
        self.shader.link()

        # bind our uniform indices
        self.shader.bind()
        self.shader.uniforms.tex0 = 0
        self.shader.unbind()

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
        # we need to convert from 3 lists with 3 sets of indices
        # to 3 lists with 1 set of indices
        # so for each index, we need to check if we already
        # have a matching vertex, and if not, make one
        vertex_bin = OrderedDict([])
        vertices = []
        texture_coords = []
        normals = []

        def process_vertex_data( bin, vertices, texture_coords, normals, data ):
            # check if we've already got this unique vertex in our list
            if data not in bin:
                # the vertex doesn't exist yet
                # insert into our vertex bin
                bin[ data ] = len(bin)

                # convert our indices into actual data
                v_index, tc_index, n_index = data

                vertices.extend(
                    list(self.obj.model.vertices[ v_index ])
                    )

                # map our texture coordinates
                # if no tc is present, insert 0.0, 0.0
                if tc_index != None:
                    texture_coords.extend(
                        list(self.obj.model.texture_coords[ tc_index ])
                        )
                else:
                    texture_coords.extend( [0.0, 0.0] )

                # map our normals
                # if no normal is present, insert 0.0, 0.0, 0.0
                if n_index != None:
                    normals.extend(
                        list(self.obj.model.normals[ n_index ])
                        )
                else:
                    normals.extend( [0.0, 0.0, 0.0] )

            # return the new index
            return bin[ data ]


        for mesh in self.obj.model.meshes:
            indices = []

            num_points = 0
            num_lines = 0
            num_faces = 0

            # check if we need to create a point mesh
            if len(mesh['points']) > 0:
                # remap each point from a random set of indices
                # to a unique vertex
                for point in mesh['points']:
                    indices.append(
                        process_vertex_data(
                            vertex_bin,
                            vertices,
                            texture_coords,
                            normals,
                            point
                            )
                        )
                num_points = len(mesh['points'])

            # check if we need to create a line mesh
            if len(mesh['lines']) > 0:
                # each line tuple is a line strip
                # the easiest way to render is to convert to
                # line segments
                def convert_to_lines( strip ):
                    result = []
                    previous = strip[ 0 ]
                    for point in strip[ 1: ]:
                        result.extend( [previous, point] )
                        previous = point
                    return result
                
                # convert each line strip into line segments
                line_segments = []
                for strip in mesh['lines']:
                    line_segments.extend( convert_to_lines( strip ) )

                # remap each point from a random set of indices
                # to a unique vertex
                for point in line_segments:
                    indices.append(
                        process_vertex_data(
                            vertex_bin,
                            vertices,
                            texture_coords,
                            normals,
                            point
                            )
                        )
                num_lines = len(line_segments)

            # check if we need to create a face mesh
            if len(mesh['faces']) > 0:
                # faces are stored as a list of triangle fans
                # we need to covnert them to triangles
                def convert_to_triangles( fan ):
                    # convert from triangle fan
                    # 0, 1, 2, 3, 4, 5
                    # to triangle list
                    # 0, 1, 2, 0, 2, 3, 0, 3, 4, 0, 4, 5
                    result = []
                    start = fan[ 0 ]
                    previous = fan[ 1 ]
                    for point in fan[ 2: ]:
                        result.extend( [start, previous, point ] )
                        previous = point
                    return result

                # convert each triangle face to triangles
                triangle_indices = []
                for face in mesh['faces']:
                    triangle_indices.extend( convert_to_triangles( face ) )

                # remap each point from a random set of indices
                # to a unique vertex
                for point in triangle_indices:
                    indices.append(
                        process_vertex_data(
                            vertex_bin,
                            vertices,
                            texture_coords,
                            normals,
                            point
                            )
                        )
                num_faces = len(triangle_indices)

            # create our index arrays
            element_vbo = (GLuint)()
            glGenBuffers( 1, element_vbo )
            glBindBuffer( GL_ELEMENT_ARRAY_BUFFER, element_vbo )
            glBufferData(
                GL_ELEMENT_ARRAY_BUFFER,
                len(indices) * 4,
                (GLuint * len(indices))(*indices),
                GL_STATIC_DRAW
                )
            glBindBuffer( GL_ELEMENT_ARRAY_BUFFER, 0 )

            # store our indices
            gl_data = (
                element_vbo,
                (0, num_points),
                (num_points, num_lines),
                (num_points + num_lines, num_faces)
                )

            # add the mesh to each of the mesh groups
            # each group has a list of meshes it owns
            for group in mesh['groups']:
                if group not in self.meshes:
                    self.meshes[ group ] = []
                self.meshes[ group ].append( gl_data )

        self.vao = (GLuint)()
        glGenVertexArrays( 1, self.vao )
        glBindVertexArray( self.vao )

        # create our global vertex data
        self.vbo = (GLuint * 3)()
        glGenBuffers( 3, self.vbo )

        # create a VBO for our vertices
        glBindBuffer( GL_ARRAY_BUFFER, self.vbo[ 0 ] )
        glBufferData(
            GL_ARRAY_BUFFER,
            len(vertices) * 4,
            (GLfloat * len(vertices))(*vertices),
            GL_STATIC_DRAW
            )
        glVertexAttribPointer( 0, 3, GL_FLOAT, GL_FALSE, 0, 0 )
        glEnableVertexAttribArray( 0 )

        # create a VBO for our texture coordinates
        glBindBuffer( GL_ARRAY_BUFFER, self.vbo[ 1 ] )
        glBufferData(
            GL_ARRAY_BUFFER,
            len(texture_coords) * 4,
            (GLfloat * len(texture_coords))(*texture_coords),
            GL_STATIC_DRAW
            )
        glVertexAttribPointer( 1, 2, GL_FLOAT, GL_FALSE, 0, 0 )
        glEnableVertexAttribArray( 1 )

        # create a VBO for our normals
        glBindBuffer( GL_ARRAY_BUFFER, self.vbo[ 2 ] )
        glBufferData(
            GL_ARRAY_BUFFER,
            len(normals) * 4,
            (GLfloat * len(normals))(*normals),
            GL_STATIC_DRAW
            )
        glVertexAttribPointer( 2, 3, GL_FLOAT, GL_FALSE, 0, 0 )
        glEnableVertexAttribArray( 2 )

        # unbind our buffers
        glBindBuffer( GL_ARRAY_BUFFER, 0 )
        glBindVertexArray( 0 )

    def render( self, projection, model_view, groups ):
        self.shader.bind()
        self.shader.uniforms.in_model_view = model_view
        self.shader.uniforms.in_projection = projection

        glBindVertexArray( self.vao )

        # iterate through the specified groups
        for group in groups:
            # get the group
            for mesh in self.meshes[ group ]:
                element_vbo, points, lines, faces = mesh

                # render the group
                glBindBuffer( GL_ELEMENT_ARRAY_BUFFER, element_vbo )

                if points[ 1 ] > 0:
                    glDrawElements(
                        GL_POINTS,
                        points[ 1 ],
                        GL_UNSIGNED_INT,
                        0
                        )
                if lines[ 1 ] > 0:
                    glDrawElements(
                        GL_LINES,
                        lines[ 1 ],
                        GL_UNSIGNED_INT,
                        points[ 1 ]
                        )
                if faces[ 1 ] > 0:
                    glDrawElements(
                        GL_TRIANGLES,
                        faces[ 1 ],
                        GL_UNSIGNED_INT,
                        points[ 1 ] + lines[ 1 ]
                        )


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

