#version 150

// inputs
uniform mat4 in_model_view;
uniform mat4 in_projection;

uniform float in_fraction;

in vec3 in_position_1;
in vec3 in_normal_1;
in vec3 in_position_2;
in vec3 in_normal_2;
in vec2 in_texture_coord;

// outputs
out vec3 ex_normal;
out vec2 ex_texture_coord;

void main()
{
    // interpolate position
    vec4 v = mix( vec4(in_position_1, 1.0), vec4(in_position_2, 1.0), in_fraction );
    gl_Position = in_projection * in_model_view * v;

    // interpolate normals
    ex_normal = normalize( mix( vec4(in_normal_1, 1.0), vec4(in_normal_2, 1.0), in_fraction ) ).xyz;

    // update our texture coordinate
    // we should include a texture matrix here
    ex_texture_coord = in_texture_coord;
}
