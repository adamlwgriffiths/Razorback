from collections import namedtuple

import numpy

from pymesh.md5.common import compute_quaternion_w
from pyrr import quaternion


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
        self.positions = None
        self.orientations = None

        self._build_frame_skeleton( md5, frame )

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
        self.parents = numpy.empty( md5.hierarchy.num_joints )
        self.positions = numpy.empty( (md5.hierarchy.num_joints, 3) )
        self.orientations = numpy.empty( (md5.hierarchy.num_joints, 4) )

        for index in range( md5.hierarchy.num_joints ):
            self.parents[ index ] = md5.hierarchy.parent_indices[ index ]

            position = self.positions[ index ]
            position[:] = frame.positions[ index ].copy()
            mask = (position == False)
            position[ mask ] = md5.base_frame.positions[ index ][ mask ]

            orientation = self.orientations[ index ]
            orientation[:] = frame.orientations[ index ].copy()
            mask = (orientation == False)
            orientation[ mask ] = md5.base_frame.orientations[ index ][ mask ]

            # compute the W component of the quaternion
            orientation[ 3 ] = compute_quaternion_w(
                orientation[ 0 ],
                orientation[ 1 ],
                orientation[ 2 ],
                )

            # check if the joint has a parent
            if self.parents[ index ] >= 0:
                parent = self.joint( self.parents[ index ] )

                # make this joint relative to the parent
                # rotate our position by our parents
                rotated_position = quaternion.apply_to_vector(
                    parent.orientation,
                    position
                    )

                # add our parent's position
                position[:] = parent.position + rotated_position;

                # multiply our orientation by our parent's
                orientation[:] = quaternion.cross( parent.orientation, orientation )

                # normalise our orientation
                orientation[:] = quaternion.normalise( orientation )


class MD5_AnimData( object ):

    def __init__( self, md5anim ):
        super( MD5_AnimData, self ).__init__()
        
        self.md5 = md5anim
        self.frames = None
        #self.vaos = None
        #self.vbos = None

        self.load()

    def _build_frame_skeletons( self ):
        # fill in any missing frame data for each joint
        self.frames = [
            MD5_FrameSkeleton( self.md5, frame )
            for frame in self.md5.frames
            ]

    def load( self ):
        self._build_frame_skeletons()
