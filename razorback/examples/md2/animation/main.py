"""Demonstrates MD2 loading, animation and rendering
"""
# import this first to ensure pyglet is
# setup for the OpenGL core profile
from pygly.examples.core.simple.main import SimpleApplication
from pygly.examples.core.application import CoreApplication

import os
import math

from PIL import Image
import numpy
import pyglet
from pyglet.gl import *

from pygly.scene_node import SceneNode
from pygly.render_callback_node import RenderCallbackNode
import pygly.sorter
from pygly.texture.pil import PIL_Texture2D
import pygly.texture
from pyrr import matrix44
import pymesh

from razorback.md2 import MD2_Mesh


class MD2_Application( SimpleApplication ):

    def setup( self ):
        super( MD2_Application, self ).setup()

        self.setup_keyboard()

        print 'Press any key to move to the next animation'

    def setup_keyboard( self ):
        self.window.push_handlers(
            on_key_release = self.on_key_release
            )

    def on_key_release( self, *args ):
        self.increment_animation()

    def setup_viewports( self ):
        super( MD2_Application, self ).setup_viewports()

        self.colours[ 0 ] = (1.0,1.0,1.0,1.0)

    def setup_camera( self ):
        super( MD2_Application, self ).setup_camera()

        # move the camera
        self.cameras[ 0 ].transform.inertial.translate(
            [ 0.0,-3.0, 0.0 ]
            )
        # tilt the camera downward
        self.cameras[ 0 ].transform.object.rotate_x( math.pi / 8.0 )

    def setup_scene( self ):
        """Creates the scene to be rendered.
        Creates our camera, scene graph, 
        """
        # don't call 'SimpleApplication's setup_scene
        CoreApplication.setup_scene( self )

        # setup our GL state
        # enable z buffer
        glEnable( GL_DEPTH_TEST )

        # enable back face culling
        glEnable( GL_CULL_FACE )
        glCullFace( GL_BACK )

        # load our texture
        # use the PIL decoder as the pyglet one is broken
        # and loads most images as greyscale
        path = os.path.join(
            os.path.dirname( __file__ ),
            '../../data/md2/sydney.bmp'
            )
        image = Image.open( path )
        self.texture = PIL_Texture2D( GL_TEXTURE_2D )
        self.texture.bind()
        self.texture.set_min_mag_filter(
            min = GL_LINEAR,
            mag = GL_LINEAR
            )
        # load the image from PIL
        # MD2 textures are inverted
        self.texture.set_image( image, flip = False )
        self.texture.unbind()

        # create a grid of cubes
        self.grid_root = SceneNode( 'grid_root' )
        self.scene_node.add_child( self.grid_root )

        # store a list of renderables
        path = os.path.join(
            os.path.dirname( __file__ ),
            '../../data/md2/sydney.md2'
            )

        self.mesh_node = RenderCallbackNode(
            'mesh',
            None,
            self.render_node
            )
        # rotate the mesh to face the camera
        self.mesh_node.transform.object.rotate_y( math.pi )

        self.mesh_node.mesh = MD2_Mesh( path )
        self.mesh_node.mesh.load()

        # attach to our scene graph
        self.grid_root.add_child( self.mesh_node )

        # scale the node
        #self.mesh_node.transform.scale = 0.2

        # store current animation
        self.animation_number = 0
        self.set_animation( self.animation_number )

    def increment_animation( self ):
        self.animation_number += 1
        if self.animation_number >= len(self.mesh_node.mesh.animations):
            self.animation_number = 0

        self.set_animation( self.animation_number )

    def set_animation( self, number ):
        self.animation_number = number
        self.animation = pymesh.md2.MD2.animations.keys()[ number ]

        start, end  = self.mesh_node.mesh.animation_start_end_frame( self.animation )
        num_frames = self.mesh_node.mesh.num_frames

        if start >= num_frames or end >= num_frames:
            print 'Animation "%s" not present' % self.animation
            return self.set_animation( 0 )

        self.mesh_node.mesh.frame_1 = start
        self.mesh_node.mesh.frame_2 = start + 1

        # some animations have only 1 frame
        if self.mesh_node.mesh.frame_2 > end:
            self.mesh_node.mesh.frame_2 = end

        print 'Animation:', self.animation

    def step( self, dt ):
        """Updates our scene and triggers the on_draw event.
        This is scheduled in our __init__ method and
        called periodically by pyglet's event callbacks.
        We need to manually call 'on_draw' as we patched
        it our of pyglets event loop when we patched it
        out with pygly.monkey_patch.
        Because we called 'on_draw', we also need to
        perform the buffer flip at the end.
        """
        # setup the scene
        # rotate the scene nodes about their vertical axis
        self.grid_root.transform.object.rotate_y( dt * 0.2 )

        # update our frame rates
        frame_rate = self.mesh_node.mesh.frame_rate

        # increment our frame
        self.mesh_node.mesh.interpolation += dt * frame_rate

        # calculate the current and next frame
        # and the blending fraction
        fraction, whole = math.modf( self.mesh_node.mesh.interpolation )
        whole = int(whole)

        # check if we're moving to the next keyframe
        if whole > 0:
            # ensure fraction remains < 1.0
            self.mesh_node.mesh.interpolation = fraction

            # increment our frames
            self.mesh_node.mesh.frame_1 += whole
            self.mesh_node.mesh.frame_2 += whole

            # get the animation's start and end frame
            start, end = self.mesh_node.mesh.animation_start_end_frame(
                self.animation
                )

            num_frames = self.mesh_node.mesh.num_frames
            if start >= num_frames:
                start = num_frames
                end = num_frames
                print 'Animation has insufficient frames'
            elif end >= num_frames:
                end = num_frames
                print 'Animation has insufficient frames'

            # ensure we don't go outside the animation
            animation_size = (end - start) + 1
            if self.mesh_node.mesh.frame_1 > end:
                self.mesh_node.mesh.frame_1 -= animation_size

            if self.mesh_node.mesh.frame_2 > end:
                self.mesh_node.mesh.frame_2 -= animation_size

        # this will trigger the draw event and buffer flip
        CoreApplication.step( self, dt )

    def render_scene( self, camera ):
        """Renders each renderable in the scene
        using the current projection and model
        view matrix.
        The original GL state will be restored
        upon leaving this function.
        """
        projection = camera.view_matrix.matrix
        model_view = camera.model_view

        # bind our diffuse texture
        glActiveTexture( GL_TEXTURE0 )
        self.texture.bind()

        # update the model view
        world_matrix = self.mesh_node.world_transform.matrix
        current_mv = matrix44.multiply(
            world_matrix,
            model_view
            )

        # render a cube
        self.mesh_node.render(
            projection = projection,
            model_view = current_mv
            )

        glActiveTexture( GL_TEXTURE0 )
        self.texture.unbind()

    def render_node( self, node, **kwargs ):
        node.mesh.render( **kwargs )


def main():
    """Main function entry point.
    Simple creates the Application and
    calls 'run'.
    Also ensures the window is closed at the end.
    """
    # create app
    app = MD2_Application()
    app.run()
    app.window.close()


if __name__ == "__main__":
    main()

