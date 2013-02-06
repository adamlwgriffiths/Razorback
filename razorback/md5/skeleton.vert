#version 150

// inputs
in uint in_index;

uniform mat4 in_model_view;
uniform mat4 in_projection;

uniform samplerBuffer in_bone_matrices;

mat4 construct_matrix( samplerBuffer sampler, int weight_index )
{
    mat4 matrix = mat4(
        texelFetch( sampler, (weight_index * 4) ),
        texelFetch( sampler, (weight_index * 4) + 1 ),
        texelFetch( sampler, (weight_index * 4) + 2 ),
        texelFetch( sampler, (weight_index * 4) + 3 )
        );
    return matrix;
}

mat4 get_bone_matrix( int weight_index )
{
    return construct_matrix( in_bone_matrices, weight_index );
}

vec4 get_bone_quaternion( int weight_index )
{
    return texelFetch( in_bone_matrices, (weight_index * 2) + 0 );
}

vec3 get_bone_position( int weight_index )
{
    return texelFetch( in_bone_matrices, (weight_index * 2) + 1 ).xyz;
}

void main()
{
    /*
    // construct our animation matrix
    mat4 mat = get_bone_matrix( int(in_index) );

    // apply the animatio matrix to our bind pose vertex
    gl_Position = in_projection * in_model_view * mat * vec4( 0.0, 0.0, 0.0, 1.0 );
    */
    vec4 pos = vec4(get_bone_position( int(in_index) ), 1.0);
    gl_Position = in_projection * in_model_view * pos;
}