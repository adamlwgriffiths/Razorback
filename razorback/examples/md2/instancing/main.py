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

from razorback.md2 import MD2_Mesh


class MD2_Application( SimpleApplication ):

    def setup_viewports( self ):
        super( MD2_Application, self ).setup_viewports()

        self.colours[ 0 ] = (1.0,1.0,1.0,1.0)

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

        # create a number of cubes
        # the grid will extend from -5 to +5
        x,z = numpy.mgrid[
            -5:5:11j,
            -5:5:11j
            ]
        x = x.flatten()
        z = z.flatten()

        positions = numpy.vstack(
            (x, numpy.zeros( x.shape ), z )
            )
        positions = positions.T

        # set the distance between the models
        positions *= 4.5

        # store a list of renderables
        self.renderables = []

        path = os.path.join(
            os.path.dirname( __file__ ),
            '../../data/md2/sydney.md2'
            )

        for position in positions:
            node = RenderCallbackNode(
                'node-%s' % position,
                None,
                self.render_node
                )
            node.mesh = MD2_Mesh( path )
            node.mesh.load()

            # attach to our scene graph
            self.grid_root.add_child( node )
            self.renderables.append( node )

            # move and scale the node
            node.transform.inertial.translation = position
            node.transform.scale = 0.2

        # create a range of animation times
        # 0.0 <= x < num_frames
        self.frames = numpy.linspace(
            0.0,
            float(self.renderables[ 0 ].mesh.num_frames),
            len(positions),
            endpoint = False
            )

        # create an array that will store our frame rates
        self.frame_rate = numpy.zeros( len(self.renderables), dtype = numpy.float )

        self.last_frame = ''

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
        self.frame_rate[:] = [ mesh_node.mesh.frame_rate for mesh_node in self.renderables ]


        # increment our frame
        #self.frames += dt * fps
        self.frames += dt * self.frame_rate
        numpy.mod(
            self.frames,
            self.renderables[ 0 ].mesh.num_frames,
            self.frames
            )

        # print the animation name of the first mesh
        curr_anim = self.renderables[ 0 ].mesh.animation
        if self.last_frame != curr_anim:
            self.last_frame = curr_anim
            print 'Curren animation:', self.last_frame

        # this will trigger the draw event and buffer flip
        super( SimpleApplication, self ).step( dt )

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

        # iterate through our renderables
        for node, frame in zip(self.renderables, self.frames):
            # update the model view
            world_matrix = node.world_transform.matrix
            current_mv = matrix44.multiply(
                world_matrix,
                model_view
                )

            fraction, frame1 = math.modf( frame )
            frame2 = (frame1 + 1.0) % node.mesh.num_frames

            # update the frame
            node.mesh.frame_1 = int(frame1)
            node.mesh.frame_2 = int(frame2)
            node.mesh.interpolation = fraction

            # render a cube
            node.render(
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

