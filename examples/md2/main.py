"""Demonstrates PyGLy's functionality.
Renders a simple scene graph and controls
a viewport.
Viewport is provided without any high level
wrappers and is entirely managed through events.
"""
# import this first
from examples.core.simple.main import SimpleApplication

import math

from PIL import Image
import numpy
import pyglet
from pyglet.gl import *
import pyglet.image

from pygly.scene_node import SceneNode
from pygly.render_callback_node import RenderCallbackNode
from md2.mesh import MD2
import pygly.sorter
from pyrr import matrix44

from examples.core.application import CoreApplication


class MD2_Application( SimpleApplication ):

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
        self.texture = self.load_bmp(
            #'examples/data/md2/sydney_h.bmp',
            'examples/data/md2/colours.png',
            )

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

        for position in positions:
            node = RenderCallbackNode(
                'node-%s' % position,
                None,
                self.render_node
                )
            node.mesh = MD2( 'examples/data/md2/sydney.md2' )
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
        self.grid_root.transform.object.rotate_y( dt )

        # increment our frame
        fps = 10.0
        self.frames += dt * fps
        numpy.mod(
            self.frames,
            self.renderables[ 0 ].mesh.num_frames,
            self.frames
            )

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
        glBindTexture( GL_TEXTURE_2D, self.texture )

        # iterate through our renderables
        for node, frame in zip(self.renderables, self.frames):
            # update the model view
            world_matrix = node.world_transform.matrix
            current_mv = matrix44.multiply(
                world_matrix,
                model_view
                )

            # update the frame
            node.mesh.frame = frame

            # render a cube
            node.render(
                projection = projection,
                model_view = current_mv
                )

    def render_node( self, node, **kwargs ):
        glActiveTexture( GL_TEXTURE0 )
        glBindTexture( GL_TEXTURE_2D, self.texture )
        node.mesh.render( **kwargs )

    def load_bmp( self, filename ):
        # http://pyopengl.sourceforge.net/context/nehe6.html
        im = Image.open( filename )

        # get image meta-data (dimensions) and data
        ix, iy = im.size[0], im.size[1]
        image = im.tostring("raw", "RGB", 0, -1)

        # generate a texture ID
        texture = (GLuint)()
        glGenTextures( 1, texture )

        # bind the texture
        glBindTexture( GL_TEXTURE_2D, texture )

        glPixelStorei( GL_UNPACK_ALIGNMENT, 1 )

        # copy the texture into the current texture ID
        glTexImage2D(
            GL_TEXTURE_2D,
            0,              # mip level
            GL_RGB,        # internal format
            ix,             # width
            iy,             # height
            0,              # border
            #GL_RGBA,        # format
            GL_RGB,        # format
            GL_UNSIGNED_BYTE,   # type
            image           # data
            )

        glTexParameteri(
            GL_TEXTURE_2D,
            GL_TEXTURE_MIN_FILTER,
            GL_LINEAR
            )
        glTexParameteri(
            GL_TEXTURE_2D,
            GL_TEXTURE_MAG_FILTER,
            GL_LINEAR
            )

        glBindTexture( GL_TEXTURE_2D, 0 )

        return texture
    

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

