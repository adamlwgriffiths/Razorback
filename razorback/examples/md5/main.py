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

from pymesh.md5 import MD5_Mesh, MD5_Anim

from razorback.md5 import Mesh
from razorback.md5.skeleton import Animation, BaseFrameSkeleton, SkeletonRenderer


class MD5_Application( SimpleApplication ):

    def setup( self ):
        super( MD5_Application, self ).setup()

        self.setup_keyboard()

        print 'Press any key to move to the next animation'

    def setup_keyboard( self ):
        self.window.push_handlers(
            on_key_release = self.on_key_release
            )

    def on_key_release( self, *args ):
        self.increment_animation()

    def setup_viewports( self ):
        super( MD5_Application, self ).setup_viewports()

        self.colours[ 0 ] = (0.5,0.5,0.5,1.0)

    def setup_cameras( self ):
        super( MD5_Application, self ).setup_cameras()

        # move the camera
        self.cameras[ 0 ].transform.inertial.translate(
            #[ 0.0, 70.0, 100.0 ]
            [ 0.0,-3.0, 10.0 ]
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
        #glEnable( GL_CULL_FACE )
        glDisable( GL_CULL_FACE )
        #glCullFace( GL_BACK )

        # create a grid of cubes
        self.grid_root = SceneNode( 'grid_root' )
        self.scene_node.add_child( self.grid_root )

        self.mesh_node = RenderCallbackNode(
            'mesh',
            None,
            self.render_node
            )
        # rotate the mesh to face the camera
        self.mesh_node.transform.object.rotate_x( -math.pi * 0.5 )

        # store a list of renderables
        mesh_path = os.path.join(
            os.path.dirname( __file__ ),
            '../data/md5/boblampclean.md5mesh'
            )

        anim_path = os.path.join(
            os.path.dirname( __file__ ),
            '../data/md5/boblampclean.md5anim'
            )

        # load our md5 data
        self.md5mesh = MD5_Mesh()
        self.md5mesh.load( mesh_path )

        self.md5anim = MD5_Anim()
        self.md5anim.load( anim_path )

        # load the gl mesh
        self.mesh_node.mesh = Mesh( self.md5mesh )

        # load our bindpose
        self.mesh_node.baseframe = BaseFrameSkeleton( self.md5mesh )

        # load some test skeletons
        self.mesh_node.anim = Animation( self.md5anim )

        # set to base frame
        self.mesh_node.mesh.set_skeleton( self.mesh_node.baseframe )

        # load a skeleton renderer
        self.mesh_node.skeleton = SkeletonRenderer()
        #self.mesh_node.skeleton.set_skeleton( self.mesh_node.baseframe )
        self.mesh_node.skeleton.set_skeleton( self.mesh_node.anim.skeleton( 0 ) )

        # create a list of frames
        self.frames = [
            skeleton
            for skeleton in self.mesh_node.anim
            ]
        self.frames.append( self.mesh_node.baseframe )

        self.frame = 0
        self.time_accumulator = 0.0
        self.time_per_frame = 0.2


        # attach to our scene graph
        self.grid_root.add_child( self.mesh_node )

        # scale the node
        self.mesh_node.transform.scale = 0.5

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

        # this will trigger the draw event and buffer flip
        CoreApplication.step( self, dt )

        if self.time_accumulator == 0.0:
            self.mesh_node.mesh.set_skeleton( self.frames[ self.frame ] )
            self.mesh_node.skeleton.set_skeleton( self.frames[ self.frame ] )

        self.time_accumulator += dt
        if self.time_accumulator > self.time_per_frame:
            self.time_accumulator = 0.0

            self.frame += 1
            self.frame %= len( self.frames )


    def render_scene( self, camera ):
        """Renders each renderable in the scene
        using the current projection and model
        view matrix.
        The original GL state will be restored
        upon leaving this function.
        """
        projection = camera.view_matrix.matrix
        model_view = camera.model_view

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

    def render_node( self, node, **kwargs ):
        node.mesh.render( **kwargs )
        node.skeleton.render( **kwargs )


def main():
    """Main function entry point.
    Simple creates the Application and
    calls 'run'.
    Also ensures the window is closed at the end.
    """
    # create app
    app = MD5_Application()
    app.run()
    app.window.close()


if __name__ == "__main__":
    main()

