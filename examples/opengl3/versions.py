import pyglet

pyglet.options['shadow_window'] = False

# Specify the OpenGL version explicitly to request 3.0 features, including
# GLSL 1.3.
# Enable depth buffer and double buffering as well
config = pyglet.gl.Config(
    double_buffer = True, 
    depth_size = 24, 
    major_version = 3, 
    minor_version = 2, 
    #forward_compatible = True
    #forward_compatible = False
    )

# Create a context matching the above configuration.  Will fail if
# OpenGL 3 is not supported by the driver.
window = pyglet.window.Window(config=config, visible=False)

# Print the version of the context created.
print('OpenGL version:', window.context.get_info().get_version())
print('OpenGL 3.2 support:', window.context.get_info().have_version(3, 2))

from ctypes import *

# get GLSL version
plain = string_at(pyglet.gl.glGetString(pyglet.gl.GL_SHADING_LANGUAGE_VERSION)).split(' ')[0]
major, minor = map(int, plain.split('.'))
version = major * 100 + minor
print('GLSL Version', version)

window.close()
