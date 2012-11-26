#version 150

// inputs
uniform mat4 in_model_view;
uniform mat4 in_projection;

in vec3 in_position;
in vec3 in_normal;
in vec2 in_texture_coord;
in vec4 in_bone_weights;
in vec4 in_bone_indices;

// outputs
out vec4 ex_position;
out vec3 ex_normal;
out vec2 ex_texture_coord;

void main()
{
    // interpolate position
    gl_Position = in_projection * in_model_view * vec4( in_position, 1.0 );

    // pass data through
    ex_normal = in_normal;
    ex_texture_coord = in_texture_coord;

    ex_position = vec4( in_position, 1.0 );
}
