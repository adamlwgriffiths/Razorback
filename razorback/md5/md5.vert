#version 150

// inputs
uniform mat4 in_model_view;
uniform mat4 in_projection;

in vec3 in_position;
in vec3 in_normal;
in vec2 in_texture_coord;
in ivec4 in_bone_indices;

uniform sampler1D in_bone_weights;

// outputs
out vec4 ex_position;
out vec3 ex_normal;
out vec2 ex_texture_coord;

void main()
{
    // interpolate position
    gl_Position = in_projection * in_model_view * vec4( in_position, 1.0 );

    // animate our vertices
    // retrieve our inverse bone matrix
    mat4 inv_bone = mat4(
        texelFetch( in_bone_weights, in_bone_indices.x, 0 ),
        texelFetch( in_bone_weights, in_bone_indices.y, 0 ),
        texelFetch( in_bone_weights, in_bone_indices.z, 0 ),
        texelFetch( in_bone_weights, in_bone_indices.w, 0 )
        );

    // pass data through
    ex_normal = in_normal;
    ex_texture_coord = in_texture_coord;

    ex_position = vec4( in_position, 1.0 );
}
