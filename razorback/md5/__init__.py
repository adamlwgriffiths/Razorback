"""
http://3dgep.com/?p=1356
http://3dgep.com/?p=1053
"""

import os

from pyglet.gl import *

import numpy

from pygly.shader import Shader, ShaderProgram
import pymesh.md5

from razorback.mesh import Mesh
from razorback.md5.mesh import MD5_MeshData
from razorback.md5.anim import MD5_AnimData


"""
correcting x,y,z for opengl

joint position
pos_x, pos_y, pos_z = pos_x, pos_z, -pos_y

joint quaternion
quat_x, quat_y, quat_z, quat_w = quat_x, quat_z, -quat_y, quat_w

weight position
pos_x, pos_y, pos_z = pos_x, pos_z, -pos_y
"""



class MD5_Data( object ):
    
    shader_source = {
        'vert': open(os.path.dirname(__file__) + '/md5.vert','r').read(),
        'frag': open(os.path.dirname(__file__) + '/md5.frag','r').read(),
    }

    def __init__( self ):
        super( MD5_Data, self ).__init__()

        self.md5mesh = None
        self.md5anims = {}
        self.mesh = None
        self.anims = {}

        self.shader = ShaderProgram(
            False,
            Shader( GL_VERTEX_SHADER, MD5_Data.shader_source['vert'] ),
            Shader( GL_FRAGMENT_SHADER, MD5_Data.shader_source['frag'] )
            )

        # set our shader data
        # we MUST do this before we link the shader
        self.shader.attributes.in_position = 0
        self.shader.attributes.in_normal = 1
        self.shader.attributes.in_texture_coord = 2
        self.shader.attributes.in_bone_indices = 3
        self.shader.attributes.in_bone_weights = 4
        self.shader.frag_location( 'out_frag_colour' )

        # link the shader now
        self.shader.link()

        # bind our uniform indices
        self.shader.bind()
        self.shader.uniforms.in_diffuse = 0
        self.shader.uniforms.in_specular = 1
        self.shader.uniforms.in_normal = 2
        self.shader.uniforms.in_inverse_bone_matrices = 3
        self.shader.uniforms.in_bone_matrices = 4
        self.shader.unbind()

    def load_mesh( self, filename ):
        if self.md5mesh:
            raise ValueError( 'MD5 already loaded' )

        self.md5mesh = pymesh.md5.MD5_Mesh()
        self.md5mesh.load( filename )

        # load into opengl
        self.mesh = MD5_MeshData( self.md5mesh )

    def load_anim( self, filename ):
        anim = pymesh.md5.MD5_Anim()
        anim.load( filename )
        self.md5anims[ filename ] = anim
        
        # load into opengl
        #self.anims[ filename ] = MD5_AnimData( anim )
        self.anims = MD5_AnimData( anim )

    def render( self, projection, model_view ):
        # bind our shader and pass in our model view
        #self.shader.bind()
        self.shader.uniforms.in_model_view = model_view
        self.shader.uniforms.in_projection = projection

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

        self.load_skeleton()

    def unload( self ):
        # FIXME: this will force unload all mesh data
        # just make it that when Data is destroyed it unloads itself
        if self.data != None:
            self.data = None
            #MD5_Data.unload( self.filename )

    def load_skeleton( self ):

        self.skeleton_shader = ShaderProgram(
            False,
            Shader( GL_VERTEX_SHADER,
"""
#version 150

in uint in_index;

// inputs
uniform mat4 in_model_view;
uniform mat4 in_projection;

uniform samplerBuffer in_inverse_bone_matrices;
uniform samplerBuffer in_bone_matrices;

mat4 construct_matrix( samplerBuffer sampler, int weight_index )
{
    mat4 matrix = mat4(
        texelFetch( sampler, (weight_index * 4) ),
        texelFetch( sampler, (weight_index * 4) + 1 ),
        texelFetch( sampler, (weight_index * 4) + 2 ),
        texelFetch( sampler, (weight_index * 4) + 3 )
        );
    return matrix;
}

mat4 get_bone_matrix( int weight_index )
{
    mat4 bone_mat = construct_matrix( in_bone_matrices, weight_index );
    mat4 inv_bone_mat = construct_matrix( in_inverse_bone_matrices, weight_index );
    //return inverse(inv_bone_mat);
    return bone_mat * inv_bone_mat;
    //return inv_bone_mat;
    //return bone_mat;
    //return inv_bone_mat * bone_mat;
}

void main()
{
    // construct our animation matrix
    mat4 mat = get_bone_matrix( int(in_index) );

    // apply the animatio matrix to our bind pose vertex
    gl_Position = in_projection * in_model_view * mat * vec4( 0.0, 0.0, 0.0, 1.0 );
}

"""
),
            Shader( GL_FRAGMENT_SHADER,
"""
#version 150

// outputs
out vec4 out_frag_colour;

void main (void)
{
    out_frag_colour = vec4( 0.0, 1.0, 0.0, 1.0 );
}

"""
)
            )

        # set our shader data
        # we MUST do this before we link the shader
        self.skeleton_shader.attributes.in_index = 0
        self.skeleton_shader.frag_location( 'out_frag_colour' )

        # link the shader now
        self.skeleton_shader.link()

        # bind our uniform indices
        self.skeleton_shader.bind()
        self.skeleton_shader.uniforms.in_inverse_bone_matrices = 3
        self.skeleton_shader.uniforms.in_bone_matrices = 4
        self.skeleton_shader.unbind()

        self.vao = (GLuint)()
        glGenVertexArrays( 1, self.vao )

        glBindVertexArray( self.vao )

        self.vbo = (GLuint)()
        glGenBuffers( 1, self.vbo )

        # create a skeleton from our bones
        lines = []
        for index, joint in enumerate( self.data.md5mesh.joints ):
            if joint.parent >= 0:
                lines.append( [joint.parent, index] )
            else:
                lines.append( [index, index] )

        self.np_lines = numpy.array( lines, dtype = 'uint32' )

        glBindBuffer( GL_ARRAY_BUFFER, self.vbo )
        glBufferData(
            GL_ARRAY_BUFFER,
            self.np_lines.nbytes,
            (GLuint * self.np_lines.size)(*self.np_lines.flat),
            GL_STATIC_DRAW
            )

        # bone_indices
        glEnableVertexAttribArray( 0 )
        glVertexAttribIPointer( 0, 1, GL_UNSIGNED_INT, GL_FALSE, 0, 0 )

        glBindVertexArray( 0 )
        glBindBuffer( GL_ARRAY_BUFFER, 0 )

    def render_skeleton( self, projection, model_view ):
        self.skeleton_shader.bind()
        self.skeleton_shader.uniforms.in_model_view = model_view
        self.skeleton_shader.uniforms.in_projection = projection

        glBindVertexArray( self.vao )

        glActiveTexture( GL_TEXTURE3 )
        glBindTexture( GL_TEXTURE_BUFFER, self.data.mesh.vbos.inverse_bone_matrices[ 1 ] )

        glActiveTexture( GL_TEXTURE4 )
        glBindTexture( GL_TEXTURE_BUFFER, self.data.anims.frames[ self.frame ].tbo )

        glActiveTexture( GL_TEXTURE0 )

        glDrawArrays( GL_LINES, 0, self.np_lines.size )

        glBindVertexArray( 0 )

        self.skeleton_shader.unbind()

    count = 0
    frame = 0
    def render( self, projection, model_view ):
        self.count += 1
        if self.count == 50:
            self.count = 0
            self.frame += 1
            if self.frame >= len(self.data.anims.frames):
                self.frame = 0

        if True:
            self.data.shader.bind()

            glActiveTexture( GL_TEXTURE3 )
            glBindTexture( GL_TEXTURE_BUFFER, self.data.mesh.vbos.inverse_bone_matrices[ 1 ] )

            glActiveTexture( GL_TEXTURE4 )
            glBindTexture( GL_TEXTURE_BUFFER, self.data.anims.frames[ self.frame ].tbo )

            glActiveTexture( GL_TEXTURE0 )

            # load a test frame
            #self.data.shader.uniforms.in_bone_positions = self.data.anims.frames[ 0 ].positions
            #self.data.shader.uniforms.in_bone_orientations = self.data.anims.frames[ 0 ].orientations

            self.data.render( projection, model_view )

        if True:
            self.render_skeleton( projection, model_view )

