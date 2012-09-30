'''
Created on 17/06/2011

@author: adam
This code uses a mix of code from:
http://code.activestate.com/recipes/498121-python-octree-implementation/
http://www.flipcode.com/archives/Octree_Implementation.shtml
'''

import math

import numpy

import Pyrr.Integer as Integer


# TODO: add remove node logic
# TODO: compress tress when all end nodes are the same value
# TODO: add logic to set an entire node to a specific value
# TODO: add logic to set a range to a specific value
# TODO: add colour delta logic

class OctreeLeaf( object ):
    
    
    def __init__( self, offset, size ):
        # position is the centre of the node
        self.offset = offset
        self.size = size
        
        self.value = 0
    
    def findNode( self, position, currentDepth, maxDepth ):
        """
        assert \
            position[ 0 ] >= self.offset[ 0 ] and \
            position[ 0 ] < (self.offset[ 0 ] + self.size) and \
            position[ 1 ] >= self.offset[ 1 ] and \
            position[ 1 ] < (self.offset[ 1 ] + self.size) and \
            position[ 2 ] >= self.offset[ 2 ] and \
            position[ 2 ] < (self.offset[ 2 ] + self.size)
        """
        return self
    
    def setValue( self, position, value ):
        """
        assert \
            position[ 0 ] >= self.offset[ 0 ] and \
            position[ 0 ] < (self.offset[ 0 ] + self.size) and \
            position[ 1 ] >= self.offset[ 1 ] and \
            position[ 1 ] < (self.offset[ 1 ] + self.size) and \
            position[ 2 ] >= self.offset[ 2 ] and \
            position[ 2 ] < (self.offset[ 2 ] + self.size)
        """
        self.value = value
        return
    

class OctreeNode( object ):
    nodeOffsets = [
        [ 0, 0, 0 ],
        [ 1, 0, 0 ],
        [ 0, 1, 0 ],
        [ 1, 1, 0 ],
        [ 0, 0, 1 ],
        [ 1, 0, 1 ],
        [ 0, 1, 1 ],
        [ 1, 1, 1 ]
        ]
    
    
    def __init__( self, offset, size ):
        # position is the centre of the node
        self.offset = offset
        self.size = size
        
        self.value = 0
        
        self.children = numpy.empty( 8, dtype = numpy.object )
        self.children.fill( None )
    
    def calculateChildIndex( self, position ):
        # determine which child to recurse into
        childIndex = 0;
        if position[ 0 ] >= (self.offset[ 0 ] + (self.size / 2)):
            childIndex |= 1
        if position[ 1 ] >= (self.offset[ 1 ] + (self.size / 2)):
            childIndex |= 2
        if position[ 2 ] >= (self.offset[ 2 ] + (self.size / 2)):
            childIndex |= 4;
        
        return childIndex
    
    def createChild( self, index ):
        assert self.children[ index ] == None
        
        size = self.size / 2
        
        offset = numpy.array([
            self.offset[ 0 ] + (size * self.nodeOffsets[ index ][ 0 ]),
            self.offset[ 1 ] + (size * self.nodeOffsets[ index ][ 1 ]),
            self.offset[ 2 ] + (size * self.nodeOffsets[ index ][ 2 ])
            ],
            dtype = int
            )
        #print "Creating child: index %s offset %s size %s" % (str(index), str(offset), str(size))
        if index & 1:
            assert offset[ 0 ] > self.offset[ 0 ] 
        if index & 2:
            assert offset[ 1 ] > self.offset[ 1 ]
        if index & 4:
            assert offset[ 2 ] > self.offset[ 2 ]
        
        if size == 1:
            self.children[ index ] = OctreeLeaf(
                offset = offset,
                size = size
                )
        else:
            self.children[ index ] = OctreeNode(
                offset = offset,
                size = size
                )
    
    def findNode( self, position, currentDepth, maxDepth ):
        # only recurse to the specified depth
        if currentDepth == maxDepth:
            return self
        
        # get the appropriate child
        childIndex = self.calculateChildIndex( position )
        childNode = self.children[ childIndex ]
        
        # check if the branch exists yet
        if childNode == None:
            # no child, the node must not be loaded or we've been compressed
            return self
        
        # increment our depth
        currentDepth += 1
        
        return childNode.findNode(
            position,
            currentDepth,
            maxDepth
            )
    
    def setValue( self, position, value ):
        # check if this branch is compressed and already equal
        # to the same value
        if \
            self.value != 0 and \
            self.value == value:
            # we're already this value
            # don't bother to continue
            #print "Already compressed to this value"
            return
        
        # get the appropriate child
        childIndex = self.calculateChildIndex( position )
        
        childNode = self.children[ childIndex ]
        
        # check if the branch exists yet
        if childNode == None:
            # ensure we're not compressed anymore
            if self.value != 0:
                #print "Decompressing"
                self.value = 0
            
            # no children are set
            # create our children
            self.createChild( childIndex )
            
            # get the child again
            childNode = self.children[ childIndex ]
        
        childNode.setValue( position, value )
        
        # check if we can compress
        if self.compress() == True:
            # we compressed
            # so our value is correct
            return
    
    def compress( self ):
        # check if we have 8 children yet
        if self.children.all() == False:
            # we don't have all 8 children
            # we can't compress
            return False
        
        # check if our other children are the same value
        # begin with child 0
        value = self.children[ 0 ].value
        
        for index in xrange( 8 ):
            # if a child's value differs then we can't compress
            if self.children[ index ].value != value:
                return False
        
        #print "Compressing"
        
        # assign ourself the value of our children
        self.value = value
        
        # compress our node
        self.children.fill( None )
        
        return True
    



class SVO( object ):
    
    
    def __init__( self, size ):
        super( SVO, self ).__init__()
        
        # size must be a multiple of 2
        if Integer.bitCount( size ) != 1:
            raise ValueError( "Octree size must be a power of 2" )
        
        self.size = size
        
        # calculate the max depth to get to size 1
        # depth is the power of 2 to get size
        # ie, 32 = 2^5, therefore there are 5 tiers
        self.maxDepth = int( math.log( size, 2 ) )
        
        # create an empty root
        self.root = OctreeNode(
            offset = numpy.array(
                [0, 0, 0],
                dtype = int
                ),
            size = size
            )
    
    def findNode( self, position, depth = -1 ):
        return self.root.findNode(
            position = position,
            currentDepth = 0,
            maxDepth = depth
            )
    
    def setValue( self, position, value ):
        self.root.setValue( position, value )
    
    def traverse( self, callback ):
        # traverse the tree
        # for any leaf, pass the position and value to the callback
        # for any compressed node, pass the start and end offsets
        pass
    


if __name__ == "__main__":
    # TODO: 0,0,0 is the centre
    # but if the power is 32, we end up with 33 values
    # +-16
    # ARGH
    
    power = 5
    size = int( math.pow( 2, power ) )
    print "Octree size = %i" % size
    octree = SVO( size = size )
    
    position = numpy.array( [31, 31, 31], dtype = int )
    node = octree.findNode(
        position = position,
        depth = -1
        )
    
    position = numpy.array( [31, 31, 31] ,dtype = int )
    value = position[ 0 ] * position[ 1 ] * position[ 2 ]
    octree.setValue(
        position = position,
        value = value
        )
    node = octree.findNode(
        position = position,
        depth = -1
        )
    assert node.value == value
    
    position = numpy.array( [31, 31, 30] ,dtype = int )
    node = octree.findNode(
        position = position,
        depth = -1
        )
    assert node.value == 0
    
    import random
    import time
    
    numToSet = 1500
    print "Setting %i random voxels" % numToSet
    startTime = time.time()
    for num in xrange( size ):
        x = random.randint( 0, 31 )
        y = random.randint( 0, 31 )
        z = random.randint( 0, 31 )
        
        octree.setValue(
            (x,y,z),
            1
            )
    endTime = time.time() - startTime
    print "Time: %s" % str(endTime)
    
    print "Setting %i voxels" % (size * size * size)
    startTime = time.time()
    for x in xrange( size ):
        for y in xrange( size ):
            for z in xrange( size ):
                octree.setValue( (x,y,z), 1 )
    endTime = time.time() - startTime
    print "Time: %s" % str(endTime)
    
    print "Setting same value over %i voxels" % (size * size * size)
    startTime = time.time()
    for x in xrange( size ):
        for y in xrange( size ):
            for z in xrange( size ):
                
                octree.setValue(
                    (x,y,z),
                    1
                    )
    endTime = time.time() - startTime
    print "Time: %s" % str(endTime)
    
    


