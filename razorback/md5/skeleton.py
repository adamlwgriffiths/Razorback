import os
from collections import namedtuple

import numpy
from pyglet.gl import *

from pyrr import quaternion
from pyrr import matrix44
from pygly.shader import Shader, ShaderProgram
from pymesh.md5.common import compute_quaternion_w


class Skeleton( object ):

    joint_layout = namedtuple(
        'MD5_SkeletonJoint',
        [
            'parent',
            'position',
            'orientation'
            ]
        )

    def __init__( self ):
        super( Skeleton, self ).__init__()

        self.parents = None
        self.positions = None
        self.orientations = None

    @property
    def num_joints( self ):
        return len( self.parents )

    def joint( self, index ):
        return Skeleton.joint_layout(
            self.parents[ index ],
            self.positions[ index ],
            self.orientations[ index ]
            )

    def __iter__( self ):
        return self.next()

    def next( self ):
        for index in range( self.num_joints ):
            yield self.joint( index )

    @property
    def matrices( self ):
        def generate_joint_matrix( joint ):
            # convert joint position and orientation to a matrix
            return matrix44.multiply(
                matrix44.create_from_quaternion( joint.orientation ),
                matrix44.create_from_translation( joint.position )
                )

        # generate our skeleton's joint matrices
        return numpy.array(
            [
                generate_joint_matrix( joint )
                for joint in self
                ],
            dtype = 'float32'
            )

    @property
    def inverse_matrices( self ):
        def generate_joint_matrix( joint ):
            # convert joint position and orientation to a matrix
            matrix = matrix44.multiply(
                matrix44.create_from_quaternion( joint.orientation ),
                matrix44.create_from_translation( joint.position )
                )
            return matrix44.inverse( matrix )

        # generate our skeleton's joint matrices
        return numpy.array(
            [
                generate_joint_matrix( joint )
                for joint in self
                ],
            dtype = 'float32'
            )

    @staticmethod
    def interpolate( skeleton1, skeleton2, percentage ):
        pass


class BaseFrameSkeleton( Skeleton ):

    def __init__( self, md5mesh ):
        super( BaseFrameSkeleton, self ).__init__()

        self.load( md5mesh )

    def load( self, md5mesh ):
        self.parents = md5mesh.joints.parents
        self.positions = md5mesh.joints.positions
        self.orientations = md5mesh.joints.orientations


class KeyframeSkeleton( Skeleton ):

    def __init__( self, md5anim, frame ):
        super( KeyframeSkeleton, self ).__init__()

        self.load( md5anim, frame )

    def load( self, md5anim, frame ):
        # we don't need to upload the parents values
        # so just leave as 'int'
        # the parent can be negative (root is -1), so it must be signed
        self.parents = numpy.empty( md5anim.hierarchy.num_joints, dtype = 'int' )
        self.positions = numpy.empty( (md5anim.hierarchy.num_joints, 3), dtype = 'float32' )
        self.orientations = numpy.empty( (md5anim.hierarchy.num_joints, 4), dtype = 'float32' )

        for index, (hierarchy_joint, base_frame_joint) in enumerate(
            zip( md5anim.hierarchy, md5anim.base_frame )
            ):
            # set the parent now as we can't set it in the named tuple
            self.parents[ index ] = hierarchy_joint.parent

            # get the current joint
            joint = self.joint( index )

            # begin with the original base frame values
            joint.position[:] = base_frame_joint.position
            joint.orientation[:] = base_frame_joint.orientation

            # overlay with values from our frame
            # we know which values to get from the joint's start_index
            # and the joint's flag
            frame_index = hierarchy_joint.start_index
            if hierarchy_joint.flags & 1:
                joint.position[ 0 ] = frame.value( frame_index )
                frame_index += 1
            if hierarchy_joint.flags & 2:
                joint.position[ 1 ] = frame.value( frame_index )
                frame_index += 1
            if hierarchy_joint.flags & 4:
                joint.position[ 2 ] = frame.value( frame_index )
                frame_index += 1
            if hierarchy_joint.flags & 8:
                joint.orientation[ 0 ] = frame.value( frame_index )
                frame_index += 1
            if hierarchy_joint.flags & 16:
                joint.orientation[ 1 ] = frame.value( frame_index )
                frame_index += 1
            if hierarchy_joint.flags & 32:
                joint.orientation[ 2 ] = frame.value( frame_index )
                frame_index += 1

            # compute the W component of the quaternion
            joint.orientation[ 3 ] = compute_quaternion_w(
                joint.orientation[ 0 ],
                joint.orientation[ 1 ],
                joint.orientation[ 2 ]
                )

            # parents should always be an bone we've
            # previously calculated
            assert joint.parent < index

            # check if the joint has a parent
            if joint.parent >= 0:
                # get the parent joint
                parent = self.joint( joint.parent )

                # make this joint relative to the parent
                # rotate our position by our parents
                rotated_position = quaternion.apply_to_vector(
                    parent.orientation,
                    joint.position
                    )

                # add our parent's position
                joint.position[:] = parent.position + rotated_position;

                # multiply our orientation by our parent's
                rotated_orientation = quaternion.cross(
                    parent.orientation,
                    joint.orientation
                    )

                # normalise our orientation
                joint.orientation[:] = quaternion.normalise( rotated_orientation )


class Animation( object ):

    def __init__( self, md5anim ):
        super( Animation, self ).__init__()
        
        self.md5anim = md5anim
        self.skeletons = None

        # fill in any missing frame data for each joint
        self.skeletons = [
            KeyframeSkeleton( self.md5anim, frame )
            for frame in self.md5anim.frames
            ]

    @property
    def frame_rate( self ):
        return self.md5anim.frame_rate

    @property
    def num_frames( self ):
        return len( self.skeletons )

    def __iter__( self ):
        return self.next()

    def next( self ):
        for skeleton in self.skeletons:
            yield skeleton

    def skeleton( self, index ):
        # TODO: interpolate between animations
        return self.skeletons[ index ]


class SkeletonRenderer( object ):
    
    shader_source = {
        'vert': open(os.path.dirname(__file__) + '/skeleton.vert','r').read(),
        'frag': open(os.path.dirname(__file__) + '/skeleton.frag','r').read(),
    }

    def __init__( self ):
        super( SkeletonRenderer, self ).__init__()

        self.num_joints = None
        self.shader = None

        self.vao = (GLuint)()
        self.indices_vbo = (GLuint)()
        self.matrix_vbo = (GLuint)()
        self.matrix_tbo = (GLuint)()

        # load our shader
        self.shader = ShaderProgram(
            False,
            Shader( GL_VERTEX_SHADER, SkeletonRenderer.shader_source['vert'] ),
            Shader( GL_FRAGMENT_SHADER, SkeletonRenderer.shader_source['frag'] )
            )

        # set our shader data
        # we MUST do this before we link the shader
        self.shader.attributes.in_index = 0
        self.shader.frag_location( 'out_frag_colour' )

        # link the shader now
        self.shader.link()

        # bind our uniform indices
        self.shader.bind()
        self.shader.uniforms.in_bone_matrices = 0
        self.shader.unbind()

        # generate our buffers
        glGenVertexArrays( 1, self.vao )
        glGenBuffers( 1, self.indices_vbo )
        glGenBuffers( 1, self.matrix_vbo )
        glGenTextures( 1, self.matrix_tbo )

    def set_skeleton( self, skeleton ):
        self.num_joints = skeleton.num_joints

        # bone indices
        # create a skeleton from our bones
        lines = []
        for index, joint in enumerate( skeleton ):
            if joint.parent >= 0:
                lines.append( [joint.parent, index] )
            else:
                lines.append( [index, index] )
        np_lines = numpy.array( lines, dtype = 'uint32' )

        # setup our VAO
        glBindVertexArray( self.vao )

        glBindBuffer( GL_ARRAY_BUFFER, self.indices_vbo )
        glBufferData(
            GL_ARRAY_BUFFER,
            np_lines.nbytes,
            (GLuint * np_lines.size)(*np_lines.flat),
            GL_DYNAMIC_DRAW
            )

        glEnableVertexAttribArray( 0 )
        glVertexAttribIPointer( 0, 1, GL_UNSIGNED_INT, GL_FALSE, 0, 0 )

        glBindBuffer( GL_ARRAY_BUFFER, 0 )
        glBindVertexArray( 0 )


        # bone matrices
        # load the matrices into our texture buffer
        #matrices = skeleton.matrices
        matrices = numpy.zeros( (skeleton.num_joints, 2, 4), dtype = 'float32' )
        matrices[ :, 0 ] = skeleton.orientations
        matrices[ :, 1, 0:3 ] = skeleton.positions

        glBindBuffer( GL_TEXTURE_BUFFER, self.matrix_vbo )
        glBufferData(
            GL_TEXTURE_BUFFER,
            matrices.nbytes,
            (GLfloat * matrices.size)(*matrices.flat),
            GL_STATIC_DRAW
            )

        # link to our BO
        glBindTexture( GL_TEXTURE_BUFFER, self.matrix_tbo )
        glTexBuffer( GL_TEXTURE_BUFFER, GL_RGBA32F, self.matrix_vbo )

        glBindTexture( GL_TEXTURE_BUFFER, 0 )
        glBindBuffer( GL_TEXTURE_BUFFER, 0 )

    def render( self, projection, model_view ):
        if self.num_joints == None:
            raise ValueError( "Skeleton not initialised" )

        self.shader.bind()
        self.shader.uniforms.in_model_view = model_view
        self.shader.uniforms.in_projection = projection

        glBindVertexArray( self.vao )

        glActiveTexture( GL_TEXTURE0 )
        glBindTexture( GL_TEXTURE_BUFFER, self.matrix_tbo )

        glDrawArrays( GL_LINES, 0, self.num_joints * 2 )

        glBindVertexArray( 0 )

        self.shader.unbind()


