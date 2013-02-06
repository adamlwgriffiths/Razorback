"""
http://3dgep.com/?p=1356
http://3dgep.com/?p=1053
"""

import os
from collections import namedtuple

import numpy
from pyglet.gl import *

from pyrr import vector
from pyrr import quaternion
from pyrr import matrix44
from pygly.shader import Shader, ShaderProgram

from razorback.mesh import Mesh
from razorback.md5.skeleton import BaseFrameSkeleton


"""
correcting x,y,z for opengl

joint position
pos_x, pos_y, pos_z = pos_x, pos_z, -pos_y

joint quaternion
quat_x, quat_y, quat_z, quat_w = quat_x, quat_z, -quat_y, quat_w

weight position
pos_x, pos_y, pos_z = pos_x, pos_z, -pos_y
"""


class Mesh( Mesh ):

    shader_source = {
        'vert': open(os.path.dirname(__file__) + '/md5.vert','r').read(),
        'frag': open(os.path.dirname(__file__) + '/md5.frag','r').read(),
    }

    def __init__( self, md5mesh ):
        super( Mesh, self ).__init__()

        self.mesh = MeshData( md5mesh )
        self.vbo = (GLuint)()
        self.tbo = (GLuint)()
        self.shader = None

        glGenBuffers( 1, self.vbo )
        glGenTextures( 1, self.tbo )

        self.shader = ShaderProgram(
            False,
            Shader( GL_VERTEX_SHADER, Mesh.shader_source['vert'] ),
            Shader( GL_FRAGMENT_SHADER, Mesh.shader_source['frag'] )
            )

        # set our shader data
        # we MUST do this before we link the shader
        self.shader.attributes.in_normal = 0
        self.shader.attributes.in_texture_coord = 1
        self.shader.attributes.in_bone_indices = 2
        self.shader.attributes.in_bone_weights_1 = 3
        self.shader.attributes.in_bone_weights_2 = 4
        self.shader.attributes.in_bone_weights_3 = 5
        self.shader.attributes.in_bone_weights_4 = 6
        self.shader.frag_location( 'out_frag_colour' )

        # link the shader now
        self.shader.link()

        # bind our uniform indices
        self.shader.bind()
        self.shader.uniforms.in_diffuse = 0
        self.shader.uniforms.in_specular = 1
        self.shader.uniforms.in_normal = 2
        self.shader.uniforms.in_bone_matrices = 4
        self.shader.unbind()

    def set_skeleton( self, skeleton ):
        # load the matrices into our texture buffer
        #matrices = skeleton.matrices
        matrices = numpy.zeros( (skeleton.num_joints, 2, 4), dtype = 'float32' )
        matrices[ :, 0 ] = skeleton.orientations
        matrices[ :, 1, 0:3 ] = skeleton.positions

        glBindBuffer( GL_TEXTURE_BUFFER, self.vbo )
        glBufferData(
            GL_TEXTURE_BUFFER,
            matrices.nbytes,
            (GLfloat * matrices.size)(*matrices.flat),
            GL_STATIC_DRAW
            )

        # link to our BO
        glBindTexture( GL_TEXTURE_BUFFER, self.tbo )
        glTexBuffer( GL_TEXTURE_BUFFER, GL_RGBA32F, self.vbo )

        glBindTexture( GL_TEXTURE_BUFFER, 0 )
        glBindBuffer( GL_TEXTURE_BUFFER, 0 )

    def render( self, projection, model_view ):
        # bind our shader and pass in our model view
        self.shader.bind()
        self.shader.uniforms.in_model_view = model_view
        self.shader.uniforms.in_projection = projection

        # set our animation data
        glActiveTexture( GL_TEXTURE0 + 4 )
        glBindTexture( GL_TEXTURE_BUFFER, self.tbo )

        # render the mesh
        self.mesh.render()

        # restore state
        glActiveTexture( GL_TEXTURE0 + 3 )
        glBindTexture( GL_TEXTURE_BUFFER, 0 )

        glActiveTexture( GL_TEXTURE0 )
        self.shader.unbind()




class MeshData( object ):

    mesh_layout = namedtuple(
        'MD5_MeshData',
        [
            'normals',
            'tcs',
            'bone_indices',
            'weights',
            'indices'
            ]
        )


    def __init__( self, md5mesh ):
        super( MeshData, self ).__init__()

        self.md5mesh = md5mesh
        self.vaos = None
        self.vbos = None

        self.load()

    def load( self ):
        mesh = self._generate_mesh()

        # load into opengl
        self.vbos = self._generate_vbos( mesh )
        self.vaos = self._generate_vaos( self.vbos )

    def _generate_mesh( self ):
        def prepare_submesh( mesh ):
            tcs = mesh.tcs
            # store weights as [pos.x, pos,y, pos.z, bias] * 4
            weights = numpy.zeros( (mesh.num_verts, 4, 4), dtype = 'float32' )
            #bone_indices = numpy.zeros( (mesh.num_verts, 4), dtype = 'uint32' )
            bone_indices = numpy.zeros( (mesh.num_verts, 4), dtype = 'float32' )

            # iterate through each vertex and generate our
            # vertex position, texture coordinate, bone index and
            # bone weights
            for vert_index, (vertex, vertex_weight, bone_index) in enumerate( 
                zip( mesh.vertices, weights, bone_indices )
                ):
                for weight_index in range( vertex.weight_count ):
                    # we only support 4 bones per vertex
                    # this is so we can fit it into a vec4
                    if weight_index >= 4:
                        print 'Too many weights for vertex! %i' % vertex.weight_count
                        break

                    weight = mesh.weight( vertex.start_weight + weight_index )

                    vertex_weight[ weight_index ][ 0:3 ] = weight.position
                    vertex_weight[ weight_index ][ 3 ] = weight.bias
                    bone_index[ weight_index ] = weight.joint

            return ( tcs, weights, bone_indices )

        """
        def prepare_normals( mesh, positions ):
            def generate_normals( positions, triangles ):
                normals = numpy.zeros( positions.shape, dtype = 'float32' )

                # generate a normal for each triangle
                for triangle in triangles:
                    v1, v2, v3 = positions[ triangle[ 0 ] ]
                    v2 = positions[ triangle[ 1 ] ]
                    v3 = positions[ triangle[ 2 ] ]

                    normal = vector.generate_normals(
                        v1,
                        v2,
                        v3,
                        normalise_result = False
                        )

                    normals[ triangle[ 0 ] ] += normal
                    normals[ triangle[ 1 ] ] += normal
                    normals[ triangle[ 2 ] ] += normal

                return normals

            def generate_bind_pose_normals( mesh, normals ):
                # convert the normals to bind-pose position
                for vert_index, vertex in enumerate( mesh.vertices ):
                    # retrieve our calculated normal
                    # normalise the normal
                    normal = vector.normalise( normals[ vert_index ] )

                    # clear our stored normal
                    # we want to store a bind pose normal
                    normals[ vert_index ] = [ 0.0, 0.0, 0.0 ]

                    # convert to bind-pose
                    # this is very similar to prepare_mesh
                    for weight_index in range( vertex.weight_count ):
                        weight = mesh.weight( vertex.start_weight + weight_index )
                        joint = self.md5mesh.joint( weight.joint )

                        # rotate the normal by the joint
                        rotated_position = quaternion.apply_to_vector(
                            joint.orientation,
                            normal
                            )

                        normals[ vert_index ] += rotated_position * weight.bias

                return normals

            normals = generate_normals( positions, mesh.tris )
            normals = generate_bind_pose_normals( mesh, normals )

            return normals
        """

        # prepare our mesh vertex data
        mesh_data = MeshData.mesh_layout(
            # normals
            numpy.empty( (self.md5mesh.num_verts, 3), dtype = 'float32' ),
            # tcs
            numpy.empty( (self.md5mesh.num_verts, 2), dtype = 'float32' ),
            # bone_indices
            #numpy.empty( (self.md5mesh.num_verts, 4), dtype = 'uint32' ),
            numpy.empty( (self.md5mesh.num_verts, 4), dtype = 'float32' ),
            # weights
            numpy.empty( (self.md5mesh.num_verts, 4, 4), dtype = 'float32' ),
            # indices
            numpy.empty( (self.md5mesh.num_tris, 3), dtype = 'uint32' )
            )

        current_vert_offset = 0
        current_tri_offset = 0
        for mesh in self.md5mesh.meshes:
            # generate the bind pose
            # and after that, use the bind pose to generate our normals
            tcs, weights, bone_indices = prepare_submesh( mesh )
            #normals = prepare_normals( mesh, positions )

            # write to our arrays
            start, end = current_vert_offset, current_vert_offset + mesh.num_verts

            #mesh_data.normals[ start : end ] = normals
            mesh_data.tcs[ start : end ] = tcs
            mesh_data.weights[ start : end ] = weights
            mesh_data.bone_indices[ start : end ] = bone_indices

            # increment our current offset by the number of vertices
            current_vert_offset += mesh.num_verts

            # store our indices
            start, end = current_tri_offset, current_tri_offset + mesh.num_tris

            mesh_data.indices[ start : end ] = mesh.tris

            # increment our current offset by the number of vertices
            current_tri_offset += mesh.num_tris

        return mesh_data

    def _generate_vbos( self, bindpose ):
        def fill_array_buffer( vbo, data, gltype ):
            glBindBuffer( GL_ARRAY_BUFFER, vbo )
            glBufferData(
                GL_ARRAY_BUFFER,
                data.nbytes,
                (gltype * data.size)(*data.flat),
                GL_STATIC_DRAW
                )

        def fill_index_buffer( bo, data, gltype ):
            glBindBuffer( GL_ELEMENT_ARRAY_BUFFER, bo )
            glBufferData(
                GL_ELEMENT_ARRAY_BUFFER,
                data.nbytes,
                (gltype * data.size)(*data.flat),
                GL_STATIC_DRAW
                )

        # load our vertex buffers
        # these are per-vertex values
        vbos = (GLuint * 5)()
        glGenBuffers( len(vbos), vbos )
        #fill_array_buffer( vbos[ 0 ], bindpose.normals, GLfloat )
        fill_array_buffer( vbos[ 1 ], bindpose.tcs, GLfloat )
        #fill_array_buffer( vbos[ 2 ], bindpose.bone_indices, GLuint )
        fill_array_buffer( vbos[ 2 ], bindpose.bone_indices, GLfloat )
        fill_array_buffer( vbos[ 3 ], bindpose.weights, GLfloat )

        # triangle indices
        fill_index_buffer( vbos[ 4 ], bindpose.indices, GLuint )

        # unbind
        glBindBuffer( GL_ARRAY_BUFFER, 0 )
        glBindBuffer( GL_ELEMENT_ARRAY_BUFFER, 0 )

        return MeshData.mesh_layout(
            vbos[ 0 ],
            vbos[ 1 ],
            vbos[ 2 ],
            vbos[ 3 ],
            vbos[ 4 ]
            )

    def _generate_vaos( self, vbos ):
        def calculate_offset( offset, elements, bytes ):
            return offset * elements * bytes

        # create our VAOs
        vaos = (GLuint * self.md5mesh.num_meshes)()
        glGenVertexArrays( self.md5mesh.num_meshes, vaos )

        # bind the arrays to our VAOs
        current_offset = 0
        for vao, mesh in zip( vaos, self.md5mesh.meshes ):
            glBindVertexArray( vao )

            """
            # normals
            offset = calculate_offset( current_offset, 3, 4 )
            glBindBuffer( GL_ARRAY_BUFFER, vbos.normals )
            glEnableVertexAttribArray( 0 )
            glVertexAttribPointer( 0, 3, GL_FLOAT, GL_FALSE, 0, offset )
            """

            # tcs
            offset = calculate_offset( current_offset, 2, 4 )
            glBindBuffer( GL_ARRAY_BUFFER, vbos.tcs )
            glEnableVertexAttribArray( 1 )
            glVertexAttribPointer( 1, 2, GL_FLOAT, GL_FALSE, 0, offset)

            # bone_indices
            offset = calculate_offset( current_offset, 4, 4 )
            glBindBuffer( GL_ARRAY_BUFFER, vbos.bone_indices )
            glEnableVertexAttribArray( 2 )
            #glVertexAttribIPointer( 2, 4, GL_UNSIGNED_INT, GL_FALSE, 0, offset )
            glVertexAttribPointer( 2, 4, GL_FLOAT, GL_FALSE, 0, offset )

            # weights
            offset = calculate_offset( current_offset, 16, 4 )
            stride = 16 * 4
            glBindBuffer( GL_ARRAY_BUFFER, vbos.weights )

            glEnableVertexAttribArray( 3 )
            glVertexAttribPointer( 3, 4, GL_FLOAT, GL_FALSE, stride, offset + (4 * 0) )

            glEnableVertexAttribArray( 4 )
            glVertexAttribPointer( 4, 4, GL_FLOAT, GL_FALSE, stride, offset + (4 * 4) )

            glEnableVertexAttribArray( 5 )
            glVertexAttribPointer( 5, 4, GL_FLOAT, GL_FALSE, stride, offset + (4 * 8) )

            glEnableVertexAttribArray( 6 )
            glVertexAttribPointer( 6, 4, GL_FLOAT, GL_FALSE, stride, offset + (4 * 12) )

            # increment our buffer offset to the next mesh
            current_offset += mesh.num_verts

            #break

        # unbind
        glBindVertexArray( 0 )
        glBindBuffer( GL_ARRAY_BUFFER, 0 )

        return vaos

    def render( self ):
        # bind our vertex attributes
        current_offset = 0
        for vao, mesh in zip( self.vaos, self.md5mesh.meshes ):
            # num indices = num tris * 3 indices per tri
            # offset = offset * 3 indices per tri * 4 bytes per element
            # bind our indices
            glBindVertexArray( vao )
            glBindBuffer( GL_ELEMENT_ARRAY_BUFFER, self.vbos.indices )
            glDrawElements(
                GL_TRIANGLES,
                mesh.num_tris * 3,
                GL_UNSIGNED_INT,
                current_offset * 3 * 4
                )

            current_offset += mesh.num_tris

            #break

        # reset our state
        glBindVertexArray( 0 )
        glBindBuffer( GL_ELEMENT_ARRAY_BUFFER, 0 )



