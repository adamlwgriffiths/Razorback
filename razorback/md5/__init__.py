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


"""
correcting x,y,z for opengl

joint position
pos_x, pos_y, pos_z = pos_x, pos_z, -pos_y

joint quaternion
quat_x, quat_y, quat_z, quat_w = quat_x, quat_z, -quat_y, quat_w

weight position
pos_x, pos_y, pos_z = pos_x, pos_z, -pos_y
"""

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

    def __init__( self, md5mesh ):
        super( MD5_MeshData, self ).__init__()
        
        self.md5 = md5mesh
        self.vaos = None
        self.vbos = None

        self.load()

    def _prepare_submesh( self, mesh ):
        positions = numpy.zeros( (mesh.num_verts, 3), dtype = 'float32' )
        tcs = mesh.tcs
        bone_indices = numpy.zeros( (mesh.num_verts, 4), dtype = 'float32' )
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
                bone_indices[ vert_index ][ weight_index ] = float( weight.joint )
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

    def _generate_vbos( self, bindpose ):
        def fill_buffer( vbo, data, gltype ):
            glBindBuffer( GL_ARRAY_BUFFER, vbo )
            glBufferData(
                GL_ARRAY_BUFFER,
                data.nbytes,
                (gltype * data.size)(*data.flat),
                GL_STATIC_DRAW
                )

        vbos = (GLuint * 6)()
        glGenBuffers( len(vbos), vbos )

        # load our buffers
        fill_buffer( vbos[ 0 ], bindpose.positions, GLfloat )
        fill_buffer( vbos[ 1 ], bindpose.normals, GLfloat )
        fill_buffer( vbos[ 2 ], bindpose.tcs, GLfloat )
        fill_buffer( vbos[ 3 ], bindpose.bone_weights, GLuint )
        fill_buffer( vbos[ 4 ], bindpose.bone_indices, GLfloat )

        # triangle indices
        glBindBuffer( GL_ELEMENT_ARRAY_BUFFER, vbos[ 5 ] )
        glBufferData(
            GL_ELEMENT_ARRAY_BUFFER,
            bindpose.indices.nbytes,
            (GLuint * bindpose.indices.size)(*bindpose.indices.flat),
            GL_STATIC_DRAW
            )

        # unbind
        glBindBuffer( GL_ARRAY_BUFFER, 0 )
        glBindBuffer( GL_ELEMENT_ARRAY_BUFFER, 0 )

        return MD5_MeshData.bindpose_layout(
            vbos[ 0 ],
            vbos[ 1 ],
            vbos[ 2 ],
            vbos[ 3 ],
            vbos[ 4 ],
            vbos[ 5 ]
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

            # bone_weights
            glBindBuffer( GL_ARRAY_BUFFER, vbos.bone_weights )
            glEnableVertexAttribArray( 3 )
            offset = calculate_offset( current_offset, 4, 4 )
            glVertexAttribPointer( 3, 4, GL_FLOAT, GL_FALSE, 0, offset )

            # bone_indices
            glBindBuffer( GL_ARRAY_BUFFER, vbos.bone_indices )
            glEnableVertexAttribArray( 4 )
            offset = calculate_offset( current_offset, 4, 4 )
            glVertexAttribIPointer( 4, 4, GL_UNSIGNED_INT, GL_FALSE, 0, offset )

            current_offset += mesh.num_verts

        # unbind
        glBindVertexArray( 0 )
        glBindBuffer( GL_ARRAY_BUFFER, 0 )

        return vaos

    def load( self ):
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
            numpy.empty( (self.md5.num_verts, 4), dtype = 'int32' ),
            # bone_weights
            numpy.empty( (self.md5.num_verts, 4), dtype = 'float32' ),
            # indices
            numpy.empty( (self.md5.num_tris, 3), dtype = 'uint32' ),
            )

        current_vert_offset = 0
        current_tri_offset = 0
        for mesh in self.md5.meshes:
            # generate the bind pose
            # and after that, use the bind pose to generate our normals
            _positions, _tcs, _bone_indices, _bone_weights = self._prepare_submesh( mesh )
            _normals = self._prepare_normals( mesh, _positions )

            # write to our arrays
            start, end = current_vert_offset, current_vert_offset + mesh.num_verts

            bindpose.positions[ start : end ] = _positions
            bindpose.normals[ start : end ] = _normals
            bindpose.tcs[ start : end ] = _tcs
            bindpose.bone_indices[ start : end ] = _bone_indices
            bindpose.bone_weights[ start : end ] = _bone_weights

            # store our indices
            start, end = current_tri_offset, current_tri_offset + mesh.num_tris
            bindpose.indices[ start : end ] = mesh.tris

            # increment our current offset by the number of vertices
            # in this mesh
            current_vert_offset += mesh.num_verts
            current_tri_offset += mesh.num_tris

        # load into opengl
        self.vbos = self._generate_vbos( bindpose )

        # create vaos for each mesh to simplify rendering
        self.vaos = self._generate_vaos( self.vbos )

        return

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
                for joint in md5.joints
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

        # check the shader material
        # if the material has no extension
        # add .tga
        pass


class MD5_Data( object ):
    
    shader_source = {
        'vert': open(os.path.dirname(__file__) + '/md5.vert','r').read(),
        'frag': open(os.path.dirname(__file__) + '/md5.frag','r').read(),
    }

    def __init__( self ):
        super( MD5_Data, self ).__init__()

        self.md5mesh = None
        self.md5anims = []
        self.mesh = None

        self.shader = ShaderProgram(
            False,
            Shader( GL_VERTEX_SHADER, MD5_Data.shader_source['vert'] ),
            Shader( GL_FRAGMENT_SHADER, MD5_Data.shader_source['frag'] )
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

    def load_mesh( self, filename = None, buffer = None ):
        if self.md5mesh:
            raise ValueError( 'MD5 already loaded' )

        self.md5mesh = pymesh.md5.MD5_Mesh()
        if filename != None:
            self.md5mesh.load( filename )
        else:
            self.md5mesh.load_from_buffer( buffer )

        # load into opengl
        self.mesh = MD5_MeshData( self.md5mesh )

    def render( self, projection, model_view ):
        # bind our shader and pass in our model view
        self.shader.bind()
        self.shader.uniform_matrixf( 'in_model_view', model_view.flat )
        self.shader.uniform_matrixf( 'in_projection', projection.flat )

        # bind our vertex attributes
        current_offset = 0
        for vao, mesh in zip( self.mesh.vaos, self.md5mesh.meshes ):
            # bind the mesh VAO
            glBindVertexArray( vao )
            
            # bind our indices
            glBindBuffer( GL_ELEMENT_ARRAY_BUFFER, self.mesh.vbos.indices )

            # num indices = num tris * 3 indices per tri
            num_indices = mesh.num_tris * 3
            # offset = offset * 3 indices per tri * 4 bytes per element
            offset = current_offset * 3 * 4

            glDrawElements(
                GL_TRIANGLES,
                mesh.num_tris * 3,
                GL_UNSIGNED_INT,
                offset
                )

            current_offset += mesh.num_tris

        # reset our state
        glBindVertexArray( 0 )
        glBindBuffer( GL_ELEMENT_ARRAY_BUFFER, 0 )
        self.shader.unbind()


class MD5_Mesh( Mesh ):


    def __init__( self, filename ):
        super( MD5_Mesh, self ).__init__()

        self.filename = filename
        self.data = None

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
        self.data.render( projection, model_view )

