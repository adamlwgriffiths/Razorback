'''
Renders axis information for visualising 3D coordinates.

.. moduleauthor:: Adam Griffiths <adam.lw.griffiths@gmail.com>
'''

from itertools import repeat

from pyglet.gl import *
import pyglet.graphics
import numpy


# create a shader


# create our geometry
x_arrow = numpy.array(
    [
        # axis
         0.0, 0.0, 0.0,
         1.0, 0.0, 0.0,
        # arrow head
         0.7, 0.3, 0.0,
         1.0, 0.0, 0.0,
         0.7,-0.3, 0.0,
         1.0, 0.0, 0.0,
        ],
    dtype = numpy.float
    )

y_arrow = numpy.array(
    [
        # axis
         0.0, 0.0, 0.0,
         0.0, 1.0, 0.0,
        # arrow head
        -0.3, 0.7, 0.0,
         0.0, 1.0, 0.0,
         0.3, 0.7, 0.0,
         0.0, 1.0, 0.0,
        ],
    dtype = numpy.float
    )

z_arrow = numpy.array(
    [
        # Z axis
         0.0, 0.0, 0.0,
         0.0, 0.0, 1.0,
        # arrow
         0.0,-0.3, 0.7,
         0.0, 0.0, 1.0,
         0.0, 0.3, 0.7,
         0.0, 0.0, 1.0,
        ],
    dtype = numpy.float
    )

x_label = numpy.array(
    [
        # X
        # \
         1.0, 0.2, 0.0,
         1.4,-0.2, 0.0,
        # /
         1.0,-0.2, 0.0,
         1.4, 0.2, 0.0,
        ],
    dtype = numpy.float
    )

y_label = numpy.array(
    [
        # Y
        # \
        -0.2, 1.4, 0.0,
         0.0, 1.2, 0.0,
        # /
         0.0, 1.2, 0.0,
         0.2, 1.4, 0.0,
        # |
         0.0, 1.2, 0.0,
         0.0, 1.0, 0.0,
        ],
    dtype = numpy.float
    )

z_label = numpy.array(
    [
        # Z
        # -
         0.0, 0.2, 1.0,
         0.0, 0.2, 1.4,
        # /
         0.0, 0.2, 1.4,
         0.0,-0.2, 1.0,
        # -
         0.0,-0.2, 1.0,
         0.0,-0.2, 1.4,
        ],
    dtype = numpy.float
    )

# compile our vertices together
vertices = numpy.concatenate(
    (x_arrow, y_arrow, z_arrow, x_label, y_label, z_label )
    )

# generate our vertex attributes
# these attributes assign each vertex to an
# axis (X,Y,Z)
colour_attributes = numpy.repeat(
    [ 1.0, 2.0, 3.0 ],
    [
        ((x_arrow.size + x_label.size) / 3),
        ((y_arrow.size + y_label.size) / 3),
        ((z_arrow.size + z_label.size) / 3),
        ]
    )

# assign each axis a colour
x_colour = [ 1.0, 0.0, 0.0 ]
y_colour = [ 0.0, 1.0, 0.0 ]
z_colour = [ 0.0, 0.0, 1.0 ]


# create a vertex list
vertex_list = pyglet.graphics.vertex_list(
    ( 'v3f/static', vertices.flat ),
    ( 'Xg1f', colour_attributes.flat ),
    )


def render( projection, modelview  ):
    """Renders the axis arrows and labels.
    """
    glPushAttrib( GL_LINE_BIT )

    # change the line width
    glLineWidth( 5.0 )

    global vertex_list
    vertex_list.draw( GL_LINES )

    # reset our gl state
    glPopAttrib()

