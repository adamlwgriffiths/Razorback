import os
import math
from collections import namedtuple

import numpy
from pyglet.gl import *

from pygly.shader import Shader, ShaderProgram
from pygly.texture import Texture2D
import pygly.texture
import pyrr.matrix44
import pyrr.vector
import pyrr.quaternion
import pymesh.md5

from razorback.mesh import Mesh


class MD5_MeshData( object ):

    bindpose_layout = namedtuple(
        'MD5_BindPose',
        [
            'positions',
            'normals',
            'tcs',
            'bone_indices',
            'bone_weights',
            'indices'
            ]
        )

    buffer_objects = namedtuple(
        'MD5_BufferObjects',
        [
            'positions',
            'normals',
            'tcs',
            'bone_indices',
            'bone_weights',
            'inverse_bone_matrices',
            'indices'
            ]
        )

    def __init__( self, md5mesh ):
        super( MD5_MeshData, self ).__init__()
        
        self.md5 = md5mesh
        self.vaos = None
        self.vbos = None

        self.load()

    def _prepare_submesh( self, mesh ):
        positions = numpy.zeros( (mesh.num_verts, 3), dtype = 'float32' )
        tcs = mesh.tcs
        bone_indices = numpy.zeros( (mesh.num_verts, 4), dtype = 'uint32' )
        bone_weights = numpy.zeros( (mesh.num_verts, 4), dtype = 'float32' )

        # iterate through each vertex and generate our
        # vertex position, texture coordinate, bone index and
        # bone weights
        for vert_index, vertex in enumerate( mesh.vertices ):
            for weight_index in range( vertex.weight_count ):
                # we only support 4 bones per vertex
                # this is so we can fit it into a vec4
                if weight_index >= 4:
                    print 'Too many weights for vertex! %i' % vertex.weight_count
                    break

                weight = mesh.weight( vertex.start_weight + weight_index )
                joint = self.md5.joint( weight.joint )

                # rotate the weight position by the joint quaternion
                rotated_position = pyrr.quaternion.apply_to_vector(
                    joint.orientation,
                    weight.position
                    )

                # add the rotated position to the joint position
                # apply weight bias and add to vertex position
                positions[ vert_index ] += ( joint.position + rotated_position ) * weight.bias
                bone_indices[ vert_index ][ weight_index ] = weight.joint
                bone_weights[ vert_index ][ weight_index ] = weight.bias

        return (
            positions,
            tcs,
            bone_indices,
            bone_weights
            )

    def _prepare_normals( self, mesh, positions ):
        def generate_normals( positions, triangles ):
            normals = numpy.zeros( positions.shape, dtype = 'float32' )

            # generate a normal for each triangle
            for triangle in triangles:
                v1, v2, v3 = positions[ triangle[ 0 ] ]
                v2 = positions[ triangle[ 1 ] ]
                v3 = positions[ triangle[ 2 ] ]

                normal = pyrr.vector.generate_normals(
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
                normal = pyrr.vector.normalise( normals[ vert_index ] )

                # clear our stored normal
                # we want to store a bind pose normal
                normals[ vert_index ] = [ 0.0, 0.0, 0.0 ]

                # convert to bind-pose
                # this is very similar to prepare_mesh
                for weight_index in range( vertex.weight_count ):
                    weight = mesh.weight( vertex.start_weight + weight_index )
                    joint = self.md5.joint( weight.joint )

                    # rotate the normal by the joint
                    rotated_position = pyrr.quaternion.apply_to_vector(
                        joint.orientation,
                        normal
                        )

                    normals[ vert_index ] += rotated_position * weight.bias

            return normals

        normals = generate_normals( positions, mesh.tris )
        normals = generate_bind_pose_normals( mesh, normals )

        return normals

    def _generate_vbos( self, bindpose, inverse_bone_matrices ):
        def fill_array_buffer( vbo, data, gltype ):
            glBindBuffer( GL_ARRAY_BUFFER, vbo )
            glBufferData(
                GL_ARRAY_BUFFER,
                data.nbytes,
                (gltype * data.size)(*data.flat),
                GL_STATIC_DRAW
                )

        def fill_texture_buffer( vbo, tbo, data, gltype, textureType ):
            # fill BO normally
            glBindBuffer( GL_TEXTURE_BUFFER, vbo )
            glBufferData(
                GL_TEXTURE_BUFFER,
                data.nbytes,
                (gltype * data.size)(*data.flat),
                GL_STATIC_DRAW
                )
            # bind our TBO
            glBindTexture( GL_TEXTURE_BUFFER, tbo )
            # link to our BO
            glTexBuffer( GL_TEXTURE_BUFFER, textureType, vbo )

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
        vbos = (GLuint * 7)()
        glGenBuffers( len(vbos), vbos )
        fill_array_buffer( vbos[ 0 ], bindpose.positions, GLfloat )
        fill_array_buffer( vbos[ 1 ], bindpose.normals, GLfloat )
        fill_array_buffer( vbos[ 2 ], bindpose.tcs, GLfloat )
        fill_array_buffer( vbos[ 3 ], bindpose.bone_indices, GLuint )
        fill_array_buffer( vbos[ 4 ], bindpose.bone_weights, GLfloat )

        # inverse bones
        tbo = (GLuint)()
        glGenTextures( 1, tbo )
        fill_texture_buffer( vbos[ 5 ], tbo, inverse_bone_matrices, GLfloat, GL_RGBA32F )

        # triangle indices
        fill_index_buffer( vbos[ 6 ], bindpose.indices, GLuint )

        # unbind
        glBindBuffer( GL_ARRAY_BUFFER, 0 )
        glBindBuffer( GL_TEXTURE_BUFFER, 0 )
        glBindBuffer( GL_ELEMENT_ARRAY_BUFFER, 0 )

        return MD5_MeshData.buffer_objects(
            vbos[ 0 ],
            vbos[ 1 ],
            vbos[ 2 ],
            vbos[ 3 ],
            vbos[ 4 ],
            (vbos[ 5 ], tbo),
            vbos[ 6 ]
            )

    def _generate_vaos( self, vbos ):
        def calculate_offset( offset, elements, bytes ):
            return offset * elements * bytes

        # create our VAOs
        vaos = (GLuint * self.md5.num_meshes)()
        glGenVertexArrays( self.md5.num_meshes, vaos )

        # bind the arrays to our VAOs
        current_offset = 0
        for vao, mesh in zip( vaos, self.md5.meshes ):
            glBindVertexArray( vao )

            # positions
            glBindBuffer( GL_ARRAY_BUFFER, vbos.positions )
            glEnableVertexAttribArray( 0 )
            offset = calculate_offset( current_offset, 3, 4 )
            glVertexAttribPointer( 0, 3, GL_FLOAT, GL_FALSE, 0, offset )

            # tcs
            glBindBuffer( GL_ARRAY_BUFFER, vbos.tcs )
            glEnableVertexAttribArray( 1 )
            offset = calculate_offset( current_offset, 2, 4 )
            glVertexAttribPointer( 1, 2, GL_FLOAT, GL_FALSE, 0, offset)

            # normals
            glBindBuffer( GL_ARRAY_BUFFER, vbos.normals )
            glEnableVertexAttribArray( 2 )
            offset = calculate_offset( current_offset, 3, 4 )
            glVertexAttribPointer( 2, 3, GL_FLOAT, GL_FALSE, 0, offset )

            # bone_indices
            glBindBuffer( GL_ARRAY_BUFFER, vbos.bone_indices )
            glEnableVertexAttribArray( 3 )
            offset = calculate_offset( current_offset, 4, 4 )
            glVertexAttribIPointer( 3, 4, GL_UNSIGNED_INT, GL_FALSE, 0, offset )

            # bone_weights
            glBindBuffer( GL_ARRAY_BUFFER, vbos.bone_weights )
            glEnableVertexAttribArray( 4 )
            offset = calculate_offset( current_offset, 4, 4 )
            glVertexAttribPointer( 4, 4, GL_FLOAT, GL_FALSE, 0, offset )

            # increment our buffer offset to the next mesh
            current_offset += mesh.num_verts

        # unbind
        glBindVertexArray( 0 )
        glBindBuffer( GL_ARRAY_BUFFER, 0 )

        return vaos

    def _generate_bind_pose( self ):
        # prepare our mesh vertices
        # we need to put them into the bind pose position
        bindpose = MD5_MeshData.bindpose_layout(
            # positions
            numpy.empty( (self.md5.num_verts, 3), dtype = 'float32' ),
            # normals
            numpy.empty( (self.md5.num_verts, 3), dtype = 'float32' ),
            # tcs
            numpy.empty( (self.md5.num_verts, 2), dtype = 'float32' ),
            # bone_indices
            numpy.empty( (self.md5.num_verts, 4), dtype = 'uint32' ),
            # bone_weights
            numpy.empty( (self.md5.num_verts, 4), dtype = 'float32' ),
            # indices
            numpy.empty( (self.md5.num_tris, 3), dtype = 'uint32' )
            )

        current_vert_offset = 0
        current_tri_offset = 0
        for mesh in self.md5.meshes:
            # generate the bind pose
            # and after that, use the bind pose to generate our normals
            positions, tcs, bone_indices, bone_weights = self._prepare_submesh( mesh )
            normals = self._prepare_normals( mesh, positions )

            # write to our arrays
            start, end = current_vert_offset, current_vert_offset + mesh.num_verts

            bindpose.positions[ start : end ] = positions
            bindpose.normals[ start : end ] = normals
            bindpose.tcs[ start : end ] = tcs
            bindpose.bone_indices[ start : end ] = bone_indices
            bindpose.bone_weights[ start : end ] = bone_weights

            # increment our current offset by the number of vertices
            current_vert_offset += mesh.num_verts

            # store our indices
            start, end = current_tri_offset, current_tri_offset + mesh.num_tris

            bindpose.indices[ start : end ] = mesh.tris

            # increment our current offset by the number of vertices
            current_tri_offset += mesh.num_tris

        return bindpose

    def _generate_inverse_bind_pose_matrices( self ):
        def generate_inverse_bone_matrix( joint ):
            """Generates the bind pose and stores the inverse matrix
            which is what is required for animation.
            """
            position_matrix = pyrr.matrix44.create_from_translation( joint.position )
            orientation_matrix = pyrr.matrix44.create_from_quaternion( joint.orientation )
            
            #matrix = pyrr.matrix44.multiply( position_matrix, orientation_matrix )
            matrix = pyrr.matrix44.multiply( orientation_matrix, position_matrix )

            return pyrr.matrix44.inverse( matrix )

        # generate our inverse bone matrices
        return numpy.array(
            [
                generate_inverse_bone_matrix( joint )
                for joint in self.md5.joints
                ],
            dtype = 'float32'
            )


    def load( self ):
        # prepare our mesh vertices
        # we need to put them into the bind pose position
        bind_pose = self._generate_bind_pose()

        # calculate the bone matrices
        #inverse_bone_matrices = self._generate_inverse_bind_pose_matrices( bindpose )
        inverse_bind_pose = self._generate_inverse_bind_pose_matrices()

        # load into opengl
        self.vbos = self._generate_vbos( bind_pose, inverse_bind_pose )

        # create vaos for each mesh to simplify rendering
        self.vaos = self._generate_vaos( self.vbos )

        # check the shader material
        # if the material has no extension
        # add .tga

