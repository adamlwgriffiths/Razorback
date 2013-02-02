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

        for index in range( md5.hierarchy.num_joints ):
            hierarchy_joint = md5.hierarchy.joint( index )
            base_frame_joint = md5.base_frame.bone( index )

            self.parents[ index ] = md5.hierarchy.parent_indices[ index ]

            # begin with the original base frame values
            position = self.positions[ index ]
            orientation = self.orientations[ index ]

            position[:] = base_frame_joint.position
            orientation[:] = base_frame_joint.orientation

            # overlay with values from our frame
            # we know which values to get from the joint's start_index
            # and the joint's flag
            frame_index = hierarchy_joint.start_index
            if hierarchy_joint.flags & 1:
                position[ 0 ] = frame.value( frame_index )
                frame_index += 1
            if hierarchy_joint.flags & 2:
                position[ 1 ] = frame.value( frame_index )
                frame_index += 1
            if hierarchy_joint.flags & 4:
                position[ 2 ] = frame.value( frame_index )
                frame_index += 1
            if hierarchy_joint.flags & 8:
                orientation[ 0 ] = frame.value( frame_index )
                frame_index += 1
            if hierarchy_joint.flags & 16:
                orientation[ 1 ] = frame.value( frame_index )
                frame_index += 1
            if hierarchy_joint.flags & 32:
                orientation[ 2 ] = frame.value( frame_index )
                frame_index += 1

            # compute the W component of the quaternion
            orientation[ 3 ] = compute_quaternion_w(
                orientation[ 0 ],
                orientation[ 1 ],
                orientation[ 2 ]
                )

            # parents should always be an bone we've
            # previously calculated
            assert self.parents[ index ] < index

            # check if the joint has a parent
            if self.parents[ index ] >= 0:
                parent = self.joint( self.parents[ index ] )

                # make this joint relative to the parent
                # rotate our position by our parents
                rotated_position = pyrr.quaternion.apply_to_vector(
                    parent.orientation,
                    position
                    )

                # add our parent's position
                position[:] = parent.position + rotated_position;

                # multiply our orientation by our parent's
                rotated_orientation = pyrr.quaternion.cross(
                    parent.orientation,
                    orientation
                    )

                # normalise our orientation
                orientation[:] = pyrr.quaternion.normalise( rotated_orientation )

    def _build_matrices( self, md5 ):
        def generate_joint_matrix( position, orientation ):
            # convert joint position and orientation to a matrix
            position_matrix = pyrr.matrix44.create_from_translation( position )
            orientation_matrix = pyrr.matrix44.create_from_quaternion( orientation )

            #return pyrr.matrix44.multiply( position_matrix, orientation_matrix )
            return pyrr.matrix44.multiply( orientation_matrix, position_matrix )

        # generate our frame's joint matrices
        self.matrices = numpy.array(
            [
                generate_joint_matrix( position, orientation )
                for position, orientation in zip( self.positions, self.orientations )
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
        
        self.md5 = md5anim
        self.frames = None
        #self.vaos = None
        #self.vbos = None

        self.load()

    def load( self ):
        # fill in any missing frame data for each joint
        self.frames = [
            MD5_FrameSkeleton( self.md5, frame )
            for frame in self.md5.frames
            ]

