#version 150

// inputs
uniform mat4 in_model_view;
uniform mat4 in_projection;

in vec3 in_position;
in vec3 in_normal;
in vec2 in_texture_coord;
in uvec4 in_bone_indices;
in vec4 in_bone_weights;

/*
uniform vec3 in_bone_positions[];
uniform vec4 in_bone_orientations[];
*/
uniform samplerBuffer in_inverse_bone_matrices;
uniform samplerBuffer in_bone_matrices;

// outputs
out vec4 ex_position;
out vec3 ex_normal;
out vec2 ex_texture_coord;

mat4 construct_matrix( samplerBuffer sampler, uint weight_index )
{
    mat4 matrix = mat4(
        texelFetch( sampler, int(weight_index) * 4 ),
        texelFetch( sampler, int(weight_index) * 4 + 1 ),
        texelFetch( sampler, int(weight_index) * 4 + 2 ),
        texelFetch( sampler, int(weight_index) * 4 + 3 )
        );
    return matrix;
}

mat4 get_bone_matrix( uint weight_index )
{
    mat4 bone_mat = construct_matrix( in_bone_matrices, weight_index );
    mat4 inv_bone_mat = construct_matrix( in_inverse_bone_matrices, weight_index );
    return bone_mat;// * inv_bone_mat;
    //return inv_bone_mat;
    //return bone_mat;
    //return inv_bone_mat * bone_mat;
}

void main()
{
    vec4 original_position = vec4( in_position, 1.0 );

    // ensure all weights add up to 1.0
    float final_weight = 1.0f - in_bone_weights[0] - in_bone_weights[1] - in_bone_weights[2];

    // construct our animation matrix
    /**/
    mat4 mat =  get_bone_matrix( in_bone_indices[0] ) * in_bone_weights[0];
    mat +=      get_bone_matrix( in_bone_indices[1] ) * in_bone_weights[1];
    mat +=      get_bone_matrix( in_bone_indices[2] ) * in_bone_weights[2];
    mat +=      get_bone_matrix( in_bone_indices[3] ) * final_weight;
    /**/
    
    /*
    ex_position =  (get_bone_matrix( in_bone_indices.x ) * original_position) * in_bone_weights.x;
    ex_position += (get_bone_matrix( in_bone_indices.y ) * original_position) * in_bone_weights.y;
    ex_position += (get_bone_matrix( in_bone_indices.z ) * original_position) * in_bone_weights.z;
    ex_position += (get_bone_matrix( in_bone_indices.w ) * original_position) * final_weight;
    */

    //mat4 mat = get_bone_matrix( in_bone_indices.x );

    // apply the animatio matrix to our bind pose vertex
    ex_position = mat * original_position;
    /*
    ex_position = vec4( in_position, 1.0 ) + vec4(
        mat[3][0],
        mat[3][1],
        mat[3][2],
        0.0
        );
    */
    //ex_position = original_position;

    // apply model view matrices
    gl_Position = in_projection * in_model_view * ex_position;
    //gl_Position = in_projection * in_model_view * vec4( in_position, 1.0 );

    //ex_normal = vec3( mat * vec4(in_normal, 0.0) );

    ex_texture_coord = in_texture_coord;
}
