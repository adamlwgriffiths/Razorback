from collections import namedtuple

import numpy
from pyglet.gl import *

import pyrr.quaternion
import pyrr.matrix44
from pymesh.md5.common import compute_quaternion_w


class MD5_FrameSkeleton( object ):

    joint_layout = namedtuple(
        'MD5_SkeletonJoint',
        [
            'parent',
            'position',
            'orientation'
            ]
        )

    def __init__( self, md5, frame ):
        super( MD5_FrameSkeleton, self ).__init__()

        self.parents = None
        self.matrices = None
        # TODO: remove positions and orientations
        self.positions = None
        self.orientations = None

        self.vbo = None
        self.tbo = None

        self.load( md5, frame )

    def load( self, md5, frame ):
        self._build_frame_skeleton( md5, frame )
        self._build_matrices( md5 )
        self._create_vbos()

    @property
    def num_joints( self ):
        return len( self.parents )

    def joint( self, index ):
        return MD5_FrameSkeleton.joint_layout(
            self.parents[ index ],
            self.positions[ index ],
            self.orientations[ index ]
            )

    def __iter__( self ):
        return self.next()

    def next( self ):
        for index in range( self.num_joints ):
            yield self.joint( index )

    def _build_frame_skeleton( self, md5, frame ):
        # we don't need to upload the parents values
        # so just leave as 'int'
        # the parent can be negative (root is -1), so it must be signed
        self.parents = numpy.empty( md5.hierarchy.num_joints, dtype = 'int' )
        self.positions = numpy.empty( (md5.hierarchy.num_joints, 3), dtype = 'float32' )
        self.orientations = numpy.empty( (md5.hierarchy.num_joints, 4), dtype = 'float32' )

        for index, (hierarchy_joint, base_frame_joint) in enumerate(
            zip( md5.hierarchy, md5.base_frame )
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
                rotated_position = pyrr.quaternion.apply_to_vector(
                    parent.orientation,
                    joint.position
                    )

                # add our parent's position
                joint.position[:] = parent.position + rotated_position;

                # multiply our orientation by our parent's
                rotated_orientation = pyrr.quaternion.cross(
                    parent.orientation,
                    joint.orientation
                    )

                # normalise our orientation
                joint.orientation[:] = pyrr.quaternion.normalise( rotated_orientation )

    def _build_matrices( self, md5 ):
        def generate_joint_matrix( joint ):
            # convert joint position and orientation to a matrix
            position_matrix = pyrr.matrix44.create_from_translation( joint.position )
            orientation_matrix = pyrr.matrix44.create_from_quaternion( joint.orientation )

            return pyrr.matrix44.multiply( orientation_matrix, position_matrix )

        # generate our frame's joint matrices
        self.matrices = numpy.array(
            [
                generate_joint_matrix( joint )
                for joint in self
                ],
            dtype = 'float32'
            )

    def _create_vbos( self ):
        # convert to opengl buffer
        self.vbo = (GLuint)()
        glGenBuffers( 1, self.vbo )
        glBindBuffer( GL_TEXTURE_BUFFER, self.vbo )
        glBufferData(
            GL_TEXTURE_BUFFER,
            self.matrices.nbytes,
            (GLfloat * self.matrices.size)(*self.matrices.flat),
            GL_STATIC_DRAW
            )
        # bind to a TBO
        self.tbo = (GLuint)()
        glGenTextures( 1, self.tbo )
        glBindTexture( GL_TEXTURE_BUFFER, self.tbo )
        glTexBuffer( GL_TEXTURE_BUFFER, GL_RGBA32F, self.vbo )

        # unbind buffers
        glBindBuffer( GL_TEXTURE_BUFFER, 0 )
        glBindTexture( GL_TEXTURE_BUFFER, 0 )



class MD5_AnimData( object ):

    def __init__( self, md5anim ):
        super( MD5_AnimData, self ).__init__()
        
        self.md5anim = md5anim
        self.frames = None
        #self.vaos = None
        #self.vbos = None

        self.load()

    def load( self ):
        # fill in any missing frame data for each joint
        self.frames = [
            MD5_FrameSkeleton( self.md5anim, frame )
            for frame in self.md5anim.frames
            ]

