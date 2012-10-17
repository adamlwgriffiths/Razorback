#version 150

// inputs
uniform mat4 model_view;
uniform mat4 projection;

in int in_position_index;
in int in_texture_coord_index;
in int in_normal_index;

uniform sampler1DArray in_positions;
uniform sampler1DArray in_texture_coords;
uniform sampler1DArray in_normals;

// outputs
out vec3 ex_normal;
out vec2 ex_texture_coord;

void main()
{
    ivec2 pos_size = textureSize( in_positions, 0 );
    ivec2 tex_size = textureSize( in_texture_coords, 0 );
    ivec2 nor_size = textureSize( in_normals, 0 );

    float pos = float( in_position_index ) / float( pos_size.y );
    ivec2 pos_index = ivec2(
        int( floor( pos ) ),
        int( fract( pos ) * float( pos_size.y ) )
        );
    float tex = float( in_texture_coord_index ) / float( tex_size.y );
    ivec2 tex_index = ivec2(
        int( floor( tex ) ),
        int( fract( tex ) * float( tex_size.y ) )
        );
    float nor = float( in_normal_index ) / float( nor_size.y );
    ivec2 nor_index = ivec2(
        int( floor( nor ) ),
        int( fract( nor ) * float( nor_size.y ) )
        );

    // set our vertex position
    vec3 position = texelFetch( in_positions, pos_index, 0 ).rgb;
    gl_Position = projection * model_view * vec4(position, 1.0);

    // set our normals normals
    vec3 normal = vec3( 0.0, 0.0, 0.0 );
    if ( in_normal_index > -1 )
    {
        vec3 normal = texelFetch( in_normals, nor_index, 0 ).rgb;
    }
    ex_normal = normal;

    // update our texture coordinate
    // we should include a texture matrix here
    vec2 texture_coord = vec2( 0.0, 0.0 );
    if ( in_texture_coord_index > -1 )
    {
        texture_coord = texelFetch( in_texture_coords, tex_index, 0 ).st;
    }
    ex_texture_coord = texture_coord;


    ex_normal = vec3( float(in_position_index), float(in_texture_coord_index), float(in_normal_index) );
}
