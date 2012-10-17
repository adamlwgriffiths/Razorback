import os

from pyglet.gl import *
import numpy

from pygly.shader import Shader
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
        self.shader.attribute( 0, 'in_position' )
        self.shader.attribute( 1, 'in_texture_coord' )
        self.shader.attribute( 2, 'in_normal' )
        self.shader.frag_location( 'fragColor' )
        self.shader.link()

        # bind our uniform indices
        self.shader.bind()
        self.shader.uniformi( 'tex0', 0 )
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
        raw_vertices = numpy.array( self.obj.model.vertices, dtype = 'float32' )
        raw_texture_coords = numpy.array( self.obj.model.texture_coords, dtype = 'float32' )
        raw_normals = numpy.array( self.obj.model.normals, dtype = 'float32' )


        # calculate our number of vertices
        # this way we can pre-allocate our arrays
        num_vertices = 0
        for mesh in self.obj.model.meshes:
            num_vertices += len(mesh['points'])

            # convert line strips to line segments
            # (size - 1) * 2
            for row in mesh['lines']:
                num_vertices += ((len(row) - 1) * 2)

            # convert triangle fans to triangles
            # (size - 2) *  3
            for row in mesh['faces']:
                num_vertices += ((len(row) - 2) * 3)

        vertices = numpy.empty( (num_vertices, 3), dtype = 'float32' )
        texture_coords = numpy.empty( (num_vertices, 2), dtype = 'float32' )
        normals = numpy.empty( (num_vertices, 3), dtype = 'float32' )

        current_offset = 0
        for mesh in self.obj.model.meshes:
            print 'Name:', mesh[ 'name' ],
            print 'Groups:', mesh['groups']

            initial_offset = current_offset

            # check if we need to create a point mesh
            num_point_indices = len(mesh['points'])
            if num_point_indices > 0:
                points = numpy.array( mesh['points'] )

                # ensure we don't have any 'None' values
                points = numpy.ma.masked_values( points, None ).filled( 0 ).astype('int32')

                # separate vertices, texture coords and normals
                points_v = points[ :, 0 ].repeat( 3 )
                points_t = points[ :, 1 ].repeat( 3 )
                points_n = points[ :, 2 ].repeat( 3 )

                v_d_indices = numpy.array([0,1,2], dtype = 'int32' ).tile( len(points) )
                t_d_indices = numpy.array([0,1,2], dtype = 'int32' ).tile( len(points) )
                t_d_indices = numpy.array([0,1,2], dtype = 'int32' ).tile( len(points) )

                # extract the indices
                vertices[ current_offset:num_point_indices ] = raw_vertices[ points_v, v_d_indices ]
                texture_coords[ current_offset:num_point_indices ] = raw_texture_coords[ points_t, t_d_indices ]
                normals[ current_offset:num_point_indices ] = raw_normals[ points_n, n_d_indices ]

                # increment the current offset
                current_offset += num_point_indices


            # check if we need to create a line mesh
            num_line_indices = len(mesh['lines'])
            if num_line_indices > 0:
                # each line tuple is a line strip
                # the easiest way to render is to convert to
                # line segments
                def convert_to_lines( strip ):
                    previous = strip[ 0 ]
                    for point in strip[ 1: ]:
                        yield previous
                        yield point
                        previous = point
                
                # convert each line strip into line segments
                lines = numpy.array([
                    point
                    for strip in mesh['lines']
                    for point in convert_to_lines( strip )
                    ])

                # update the number of lines
                num_line_indices = len(lines)

                # ensure we don't have any 'None' values
                lines = numpy.ma.masked_values( lines, None ).filled( 0 ).astype('int32')

                # separate vertices, texture coords and normals
                lines_v = lines[ :, 0 ]
                lines_t = lines[ :, 1 ]
                lines_n = lines[ :, 2 ]

                # extract the indices
                vertices[ current_offset:num_line_indices ] = raw_vertices[ lines_v ]
                texture_coords[ current_offset:num_line_indices ] = raw_texture_coords[ lines_t ]
                normals[ current_offset:num_line_indices ] = raw_normals[ lines_n ]

                # increment the current offset
                current_offset += num_line_indices


            # check if we need to create a face mesh
            num_face_indices = len(mesh['faces'])
            if num_face_indices > 0:
                # faces are stored as a list of triangle fans
                # we need to covnert them to triangles
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
                faces = numpy.array([
                    value
                    for triangle in mesh['faces']
                    for value in convert_to_triangles( triangle )
                    ])

                # update the number of faces
                num_face_indices = len(faces)

                # replace None with invalid values
                faces = numpy.ma.masked_values( faces, None ).filled( 0 ).astype('int32')

                # separate vertices, texture coords and normals
                faces_v = faces[ :, 0 ].repeat( 3 )
                faces_t = faces[ :, 1 ].repeat( 2 )
                faces_n = faces[ :, 2 ].repeat( 3 )

                indices3 = numpy.tile([0,1,2], num_face_indices ).astype( 'int32' )
                indices2 = numpy.tile([0,1], num_face_indices ).astype( 'int32' )

                # extract the indices
                start, end = current_offset, current_offset + num_face_indices

                extracted_v = raw_vertices[ faces_v, indices3 ].reshape( num_face_indices, 3 )
                vertices[ start:end ] = extracted_v

                if raw_texture_coords.size > 0:
                    extracted_t = raw_texture_coords[ faces_t, indices2 ].reshape( num_face_indices, 2 )
                    texture_coords[ start:end ] = extracted_t
                else:
                    texture_coords[ start:end ] = [ 0.0, 0.0 ]


                if raw_normals.size > 0:
                    extracted_n = raw_normals[ faces_n, indices3 ].reshape( num_face_indices, 3 )
                    normals[ start:end ] = extracted_n
                else:
                    normals[ start:end ] = [ 0.0, 0.0, 0.0 ]

                # increment the current offset
                current_offset += num_face_indices

            # store our indices
            gl_data = (
                (initial_offset, num_point_indices),
                (initial_offset + num_point_indices, num_line_indices),
                (initial_offset + num_point_indices + num_line_indices, num_face_indices)
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

        vertices = vertices.flatten()
        texture_coords = texture_coords.flatten()
        normals = normals.flatten()

        # create a VBO for our vertices
        glBindBuffer( GL_ARRAY_BUFFER, self.vbo[ 0 ] )
        glBufferData(
            GL_ARRAY_BUFFER,
            vertices.nbytes,
            (GLfloat * len(vertices))(*vertices.flat),
            GL_STATIC_DRAW
            )

        # create a VBO for our texture coordinates
        glBindBuffer( GL_ARRAY_BUFFER, self.vbo[ 1 ] )
        glBufferData(
            GL_ARRAY_BUFFER,
            texture_coords.nbytes,
            (GLfloat * len(texture_coords))(*texture_coords.flat),
            GL_STATIC_DRAW
            )

        # create a VBO for our normals
        glBindBuffer( GL_ARRAY_BUFFER, self.vbo[ 2 ] )
        glBufferData(
            GL_ARRAY_BUFFER,
            normals.nbytes,
            (GLfloat * len(normals))(*normals.flat),
            GL_STATIC_DRAW
            )

        # unbind our buffers
        glBindBuffer( GL_ARRAY_BUFFER, 0 )
        glBindVertexArray( 0 )

    def render( self, projection, model_view, groups ):
        self.shader.bind()
        self.shader.uniform_matrixf( 'model_view', model_view.flat )
        self.shader.uniform_matrixf( 'projection', projection.flat )

        glBindVertexArray( self.vao )

        # bind our global data
        # vertices
        glBindBuffer( GL_ARRAY_BUFFER, self.vbo[ 0 ] )
        glVertexAttribPointer( 0, 3, GL_FLOAT, GL_FALSE, 0, 0 )
        glEnableVertexAttribArray( 0 )

        # texture coords
        glBindBuffer( GL_ARRAY_BUFFER, self.vbo[ 1 ] )
        glVertexAttribPointer( 1, 2, GL_FLOAT, GL_FALSE, 0, 0 )
        glEnableVertexAttribArray( 1 )

        # normals
        glBindBuffer( GL_ARRAY_BUFFER, self.vbo[ 2 ] )
        glVertexAttribPointer( 2, 3, GL_FLOAT, GL_FALSE, 0, 0 )
        glEnableVertexAttribArray( 2 )

        # iterate through the specified groups
        for group in groups:
            # get the group
            for mesh in self.meshes[ group ]:
                points, lines, faces = mesh

                point_start, point_count = points
                line_start, line_count = lines
                face_start, face_count = faces

                if points[ 1 ] > 0:
                    glDrawArrays( GL_POINTS, point_start, point_count )
                if lines[ 1 ] > 0:
                    glDrawArrays( GL_LINES, line_start, line_count )
                if faces[ 1 ] > 0:
                    glDrawArrays( GL_TRIANGLES, face_start, face_count )

        glDisableVertexAttribArray( 0 )
        glDisableVertexAttribArray( 1 )
        glDisableVertexAttribArray( 2 )

        glBindBuffer( GL_ARRAY_BUFFER, 0 )
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

