"""Demonstrates OBJ loading and rendering
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

from razorback.obj import OBJ_Mesh


class OBJ_Application( SimpleApplication ):

    def setup_viewports( self ):
        super( OBJ_Application, self ).setup_viewports()

        self.colours[ 0 ] = (0.1,0.1,0.1,1.0)

    def setup_camera( self ):
        super( OBJ_Application, self ).setup_camera()

        # move the camera
        self.cameras[ 0 ].transform.inertial.translate(
            [ 0.0,-3.0,-5.0 ]
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

        # create a grid of cubes
        self.grid_root = SceneNode( 'grid_root' )
        self.scene_node.add_child( self.grid_root )

        # store a list of renderables
        path = os.path.join(
            os.path.dirname( __file__ ),
            '../data/obj/capsule.obj'
            )

        self.mesh_node = RenderCallbackNode(
            'mesh',
            None,
            self.render_node
            )
        # rotate the mesh to face the camera
        self.mesh_node.transform.object.rotate_y( math.pi )

        self.mesh_node.mesh = OBJ_Mesh( path )
        self.mesh_node.mesh.load()

        # attach to our scene graph
        self.grid_root.add_child( self.mesh_node )

        # scale the node
        self.mesh_node.transform.scale = 1.0

        # create a list of groups to render
        # by default, render all groups
        # this may be in-efficient if data is contained in
        # multiple groups
        self.groups = self.mesh_node.mesh.data.meshes.keys()

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
            model_view = current_mv,
            groups = self.groups
            )

    def render_node( self, node, **kwargs ):
        node.mesh.render( **kwargs )


def main():
    """Main function entry point.
    Simple creates the Application and
    calls 'run'.
    Also ensures the window is closed at the end.
    """
    # create app
    app = OBJ_Application()
    app.run()
    app.window.close()


if __name__ == "__main__":
    main()

