#version 150

// inputs
in vec3 in_position;
in vec2 in_texture_coord;
uniform mat4 model_view;
uniform mat4 projection;

uniform sampler1DArray verts1;
uniform sampler1DArray verts2;
uniform float fraction;

// outputs
out vec3 ex_normal;
out vec2 ex_texture_coord;

void main()
{
    // extract our vertex position from our textures
    vec4 v1 = vec4( texelFetch( verts1, ivec2(gl_VertexID,0), 0 ).xyz, 1.0 );
    vec4 v2 = vec4( texelFetch( verts2, ivec2(gl_VertexID,0), 0 ).xyz, 1.0 );
    vec4 n1 = vec4( texelFetch( verts1, ivec2(gl_VertexID,1), 0 ).xyz, 1.0 );
    vec4 n2 = vec4( texelFetch( verts2, ivec2(gl_VertexID,1), 0 ).xyz, 1.0 );

    // interpolate position
    vec4 v = mix( v1, v2, fraction );
    gl_Position = projection * model_view * v;

    // interpolate normals
    ex_normal = normalize( mix( n1, n2, fraction ) ).xyz;

    // update our texture coordinate
    // we should include a texture matrix here
    ex_texture_coord = in_texture_coord;
}
