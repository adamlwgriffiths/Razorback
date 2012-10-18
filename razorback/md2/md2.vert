#version 150

// inputs
in vec2 in_texture_coord;
uniform mat4 in_model_view;
uniform mat4 in_projection;

uniform sampler1DArray in_vertex_data;
uniform float in_fraction;
uniform int in_frame_1;
uniform int in_frame_2;

// outputs
out vec3 ex_normal;
out vec2 ex_texture_coord;

void main()
{
    // frames are stored in pairs of (vertices, normals)
    int frame1v = in_frame_1 * 2;
    int frame1n = (in_frame_1 * 2) + 1;
    int frame2v = in_frame_2 * 2;
    int frame2n = (in_frame_2 * 2) + 1;

    // extract our vertex position from our textures
    vec4 v1 = vec4( texelFetch( in_vertex_data, ivec2(gl_VertexID, frame1v), 0 ).xyz, 1.0 );
    vec4 v2 = vec4( texelFetch( in_vertex_data, ivec2(gl_VertexID, frame2v), 0 ).xyz, 1.0 );
    vec4 n1 = vec4( texelFetch( in_vertex_data, ivec2(gl_VertexID, frame1n), 0 ).xyz, 1.0 );
    vec4 n2 = vec4( texelFetch( in_vertex_data, ivec2(gl_VertexID, frame2n), 0 ).xyz, 1.0 );

    // interpolate position
    vec4 v = mix( v1, v2, in_fraction );
    gl_Position = in_projection * in_model_view * v;

    // interpolate normals
    ex_normal = normalize( mix( n1, n2, in_fraction ) ).xyz;

    // update our texture coordinate
    // we should include a texture matrix here
    ex_texture_coord = in_texture_coord;
}
