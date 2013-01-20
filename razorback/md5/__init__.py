"""
http://3dgep.com/?p=1356
http://3dgep.com/?p=1053
"""

import os

from pyglet.gl import *

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
        self.md5anims = []
        self.mesh = None
        self.anims = []

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
        self.shader.frag_location( 'out_frag_colour' )

        # link the shader now
        self.shader.link()

        # bind our uniform indices
        self.shader.bind()
        self.shader.uniforms.in_diffuse = 0
        self.shader.uniforms.in_bone_weights = 1
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

    def load_anim( self, filename = None, buffer = None ):
        anim = pymesh.md5.MD5_Anim()
        if filename != None:
            anim.load( filename )
        else:
            anim.load_from_buffer( buffer )

        # TODO: use a dictionary and give it a name
        
        # load into opengl
        self.anims.append( MD5_AnimData( anim ) )

    def render( self, projection, model_view ):
        # bind our shader and pass in our model view
        self.shader.bind()
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

    def unload( self ):
        # FIXME: this will force unload all mesh data
        # just make it that when Data is destroyed it unloads itself
        if self.data != None:
            self.data = None
            #MD5_Data.unload( self.filename )

    def render( self, projection, model_view ):
        self.data.render( projection, model_view )

