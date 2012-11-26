"""
http://3dgep.com/?p=1356
http://3dgep.com/?p=1053
"""

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


class MD5_Data( object ):
    
    def __init__( self ):
        super( MD5_Data, self ).__init__()

        self.md5 = None
        self.animations = []

        self.meshes = None
        self.joints = None

    def load_mesh( self, filename = None, buffer = None ):
        if self.md5:
            raise ValueError( 'MD5 already loaded' )

        self.md5 = pymesh.md5.MD5_Mesh()
        if filename != None:
            self.md5.load( filename )
        else:
            self.md5.load_from_buffer( buffer )


        def prepare_mesh( mesh, joints ):
            mesh_layout = namedtuple(
                'PreparedMesh',
                [
                    'positions',
                    'tcs',
                    'bone_indices',
                    'bone_weights'
                    ]
                )

            positions = numpy.zeros( (mesh.numverts, 3), dtype = 'float32' )
            tcs = numpy.zeros( (mesh.numverts, 2), dtype = 'float32' )
            bone_indices = numpy.zeros( (mesh.numverts, 4), dtype = 'float32' )
            bone_weights = numpy.zeros( (mesh.numverts, 4), dtype = 'float32' )

            # iterate through each vertex and generate our
            # vertex position, texture coordinate, bone index and
            # bone weights
            for vert_index, vertex in enumerate( mesh.verts ):
                # we only support 4 bones per vertex
                # this is so we can fit it into a vec4
                if vertex.weight_count > 4:
                    raise ValueError( 'Too many weights for vertex!' )

                for weight_index in range( vertex.weight_count ):
                    weight = mesh.weights[ vertex.start_weight + weight_index ]
                    joint = joints[ weight.joint ]

                    joint_position = numpy.array( joint.position )
                    joint_orientation = numpy.array( joint.orientation )
                    weight_position = numpy.array( weight.position )

                    # rotate the weight position by the joint quaternion
                    rotated_position = pyrr.quaternion.apply_to_vector(
                        joint_orientation,
                        weight_position
                        )

                    # add the rotated position to the joint position
                    # apply weight bias and add to vertex position
                    positions[ vert_index ] += ( joint_position + rotated_position ) * weight.bias
                    bone_indices[ vert_index ][ weight_index ] = float( weight.joint )
                    bone_weights[ vert_index ][ weight_index ] = weight.bias

                tcs[ vert_index ] = [ vertex.tu, vertex.tv ]

            return mesh_layout(
                positions,
                tcs,
                bone_indices,
                bone_weights
                )

        # convert our vertices into our bind pose position
        prepared_meshes = [
            prepare_mesh( mesh, self.md5.joints )
            for mesh in self.md5.meshes
            ]


        def prepare_normals( vertices, positions, triangles, weights, joints ):
            normals = numpy.zeros( (len( vertices ), 3), dtype = 'float32' )

            # generate a normal for each triangle
            for triangle in triangles:
                v1 = positions[ triangle[ 0 ] ]
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

            # convert the normals to bind-pose position
            for vert_index, vertex in enumerate( vertices ):
                # retrieve our calculated normal
                # normalise the normal
                normal = pyrr.vector.normalise( normals[ vert_index ] )

                # clear our stored normal
                # we want to store a bind pose normal
                normals[ vert_index ] = [ 0.0, 0.0, 0.0 ]

                # convert to bind-pose
                # this is very similar to prepare_mesh
                for weight_index in range( vertex.weight_count ):
                    weight = weights[ vertex.start_weight + weight_index ]
                    joint = joints[ weight.joint ]

                    joint_orientation = numpy.array( joint.orientation )

                    # rotate the normal by the joint
                    rotated_position = pyrr.quaternion.apply_to_vector(
                        joint_orientation,
                        normal
                        )

                    normals[ vert_index ] += ( rotated_position * weight.bias )

            return normals

        # create our normals for each triangle and convert to bind pose position
        prepared_normals = [
            prepare_normals(
                vanilla_mesh.verts,
                prepared_mesh.positions,
                vanilla_mesh.tris,
                vanilla_mesh.weights,
                self.md5.joints
                )
            for vanilla_mesh, prepared_mesh in zip( self.md5.meshes, prepared_meshes )
            ]

        def create_mesh_vertex_buffers(
            positions,
            normals,
            tcs,
            bone_weights,
            bone_indices,
            indices
            ):
            vbo_layout = namedtuple(
                "Mesh_VBOs",
                [
                    'vao',
                    'positions',
                    'normals',
                    'tcs',
                    'bone_weights',
                    'bone_indices',
                    'indices',
                    'num_indices'
                    ]
                )

            vbos = (GLuint * 6)()
            glGenBuffers( len(vbos), vbos )

            position_buffer = vbos[ 0 ]
            normal_buffer = vbos[ 1 ]
            tc_buffer = vbos[ 2 ]
            bone_weight_buffer = vbos[ 3 ]
            bone_indice_buffer = vbos[ 4 ]
            index_buffer = vbos[ 5 ]

            # TODO: blend these vertex buffers into a single buffer

            vao = (GLuint)()
            glGenVertexArrays( 1, vao )
            glBindVertexArray( vao )

            def load_buffer( vbo, data, gltype ):
                glBindBuffer( GL_ARRAY_BUFFER, vbo )
                glBufferData(
                    GL_ARRAY_BUFFER,
                    data.nbytes,
                    (gltype * data.size)(*data.flat),
                    GL_STATIC_DRAW
                    )

            # positions
            positions = prepared_mesh.positions
            load_buffer( position_buffer, positions, GLfloat )
            glEnableVertexAttribArray( 0 )
            glVertexAttribPointer( 0, 3, GL_FLOAT, GL_FALSE, 0, 0 )

            # normals
            load_buffer( normal_buffer, normals, GLfloat )
            glEnableVertexAttribArray( 1 )
            glVertexAttribPointer( 1, 3, GL_FLOAT, GL_FALSE, 0, 0 )

            # texture coordinates
            tcs = prepared_mesh.tcs
            load_buffer( tc_buffer, tcs, GLfloat )
            glEnableVertexAttribArray( 2 )
            glVertexAttribPointer( 2, 2, GL_FLOAT, GL_FALSE, 0, 0 )

            # bone weights
            bone_weights = prepared_mesh.bone_weights
            load_buffer( bone_weight_buffer, bone_weights, GLfloat )
            glEnableVertexAttribArray( 3 )
            glVertexAttribPointer( 3, 4, GL_FLOAT, GL_FALSE, 0, 0 )

            # bone indices
            bone_indices = prepared_mesh.bone_indices
            load_buffer( bone_indice_buffer, bone_indices, GLfloat )
            glEnableVertexAttribArray( 4 )
            glVertexAttribPointer( 4, 4, GL_FLOAT, GL_FALSE, 0, 0 )

            # triangle indices
            glBindBuffer( GL_ELEMENT_ARRAY_BUFFER, index_buffer )
            glBufferData(
                GL_ELEMENT_ARRAY_BUFFER,
                indices.nbytes,
                (GLuint * indices.size)(*indices.flat),
                GL_STATIC_DRAW
                )

            glBindVertexArray( 0 )

            return vbo_layout(
                vao,
                position_buffer,
                normal_buffer,
                tc_buffer,
                bone_weight_buffer,
                bone_indice_buffer,
                index_buffer,
                indices.size
                )

        # create our mesh vertex buffers
        self.meshes = [
            create_mesh_vertex_buffers(
                prepared_mesh.positions,
                normals,
                prepared_mesh.tcs,
                prepared_mesh.bone_weights,
                prepared_mesh.bone_indices,
                numpy.array( vanilla_mesh.tris, dtype = 'uint32' )
                )
            for vanilla_mesh, prepared_mesh, normals in zip( self.md5.meshes, prepared_meshes, prepared_normals )
            ]


        def generate_inverse_bone_matrix( joint ):
            """Generates the bind pose and stores the inverse matrix
            which is what is required for animation.
            """
            translation = pyrr.matrix44.create_from_translation( joint.position )
            rotation = pyrr.matrix44.create_from_quaternion( joint.orientation )
            matrix = pyrr.matrix44.multiply( translation, rotation )
            return pyrr.matrix44.inverse( matrix )

        # generate our inverse bone matrices
        inverse_bone_matrices = numpy.array(
            [
                generate_inverse_bone_matrix( joint )
                for joint in self.md5.joints
                ],
            dtype = 'float32'
            )

        def create_joint_texture( matrices ):
            # take the first row of each matrix
            r0 = matrices[ :, 0 ].flatten()
            r1 = matrices[ :, 0 ].flatten()
            r2 = matrices[ :, 0 ].flatten()
            r3 = matrices[ :, 0 ].flatten()

            pass


        # create our bone matrix vertex buffers
        self.joints = create_joint_texture( inverse_bone_matrices )

        # inbind our buffers
        glBindBuffer( GL_ARRAY_BUFFER, 0 )
        glBindBuffer( GL_ELEMENT_ARRAY_BUFFER, 0 )

        # check the shader material
        # if the material has no extension
        # add .tga
        pass

    def load_animation( self, filename ):
        pass


class MD5_Mesh( Mesh ):

    shader_source = {
        'vert': open(os.path.dirname(__file__) + '/md5.vert','r').read(),
        'frag': open(os.path.dirname(__file__) + '/md5.frag','r').read(),
    }

    def __init__( self, filename ):
        super( MD5_Mesh, self ).__init__()

        self.filename = filename
        self.data = None

        self.shader = ShaderProgram(
            False,
            Shader( GL_VERTEX_SHADER, MD5_Mesh.shader_source['vert'] ),
            Shader( GL_FRAGMENT_SHADER, MD5_Mesh.shader_source['frag'] )
            )

        # set our shader data
        # we MUST do this before we link the shader
        self.shader.attribute( 0, 'in_position' )
        self.shader.attribute( 1, 'in_normal' )
        self.shader.attribute( 2, 'in_texture_coord' )
        self.shader.attribute( 3, 'in_bone_weights' )
        self.shader.attribute( 4, 'in_bone_indices' )
        self.shader.frag_location( 'out_frag_colour' )

        # link the shader now
        self.shader.link()

        # bind our uniform indices
        self.shader.bind()
        self.shader.uniformi( 'in_diffuse', 0 )
        self.shader.unbind()

    def load( self ):
        if self.data == None:
            #self.data = MD5_Data.load_mesh( self.filename )
            self.data = MD5_Data()
            self.data.load_mesh( self.filename )

    def unload( self ):
        # FIXME: this will force unload all mesh data
        # just make it that when Data is destroyed it unloads itself
        if self.data != None:
            self.data = None
            #MD5_Data.unload( self.filename )

    def render( self, projection, model_view ):
        # bind our shader and pass in our model view
        self.shader.bind()
        self.shader.uniform_matrixf( 'in_model_view', model_view.flat )
        self.shader.uniform_matrixf( 'in_projection', projection.flat )

        # bind our vertex attributes
        for mesh in self.data.meshes:
            # bind the mesh VAO
            glBindVertexArray( mesh.vao )
            glBindBuffer( GL_ELEMENT_ARRAY_BUFFER, mesh.indices )

            # TODO: bind our diffuse texture to TEX0

            glDrawElements(
                GL_TRIANGLES,
                mesh.num_indices,
                GL_UNSIGNED_INT,
                0
                )
            break

        # reset our state
        glBindVertexArray( 0 )
        glBindBuffer( GL_ELEMENT_ARRAY_BUFFER, 0 )
        glBindBuffer( GL_ARRAY_BUFFER, 0 )
        self.shader.unbind()

