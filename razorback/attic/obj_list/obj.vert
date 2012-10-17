#version 150

// inputs
in vec3 in_position;
in vec2 in_texture_coord;
in vec3 in_normal;
uniform mat4 model_view;
uniform mat4 projection;

// outputs
out vec3 ex_normal;
out vec2 ex_texture_coord;

void main()
{
    // set our vertex position
    gl_Position = projection * model_view * vec4(in_position, 1.0);

    // set our normals normals
    ex_normal = in_normal;

    // update our texture coordinate
    // we should include a texture matrix here
    ex_texture_coord = in_texture_coord;
}
