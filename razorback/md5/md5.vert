#version 150

// inputs
uniform mat4 in_model_view;
uniform mat4 in_projection;

in vec3 in_position;
in vec3 in_normal;
in vec2 in_texture_coord;
in ivec4 in_bone_indices;
in vec4 in_bone_weights;

/*
uniform vec3 in_bone_positions[];
uniform vec4 in_bone_orientations[];
*/
uniform samplerBuffer in_inverse_bone_matrices;
uniform samplerBuffer in_bone_joints;

// outputs
out vec4 ex_position;
out vec3 ex_normal;
out vec2 ex_texture_coord;

mat4 constructMatrix( samplerBuffer sampler, int weight_index )
{
    return mat4(
        texelFetch( sampler, weight_index * 4 ),
        texelFetch( sampler, weight_index * 4 + 1 ),
        texelFetch( sampler, weight_index * 4 + 2 ),
        texelFetch( sampler, weight_index * 4 + 3 )
        );
}

mat4 getBoneMatrix( int weight_index )
{
    mat4 bone_mat = constructMatrix( in_bone_joints, weight_index );
    mat4 inv_bone_mat = constructMatrix( in_inverse_bone_matrices, weight_index );
    //return bone_mat * inv_bone_mat;
    return inv_bone_mat * bone_mat;
    //return inv_bone_mat;
    //return bone_mat;
}

void main()
{
    ex_position = vec4( in_position, 1.0 );

    
    float final_weight = 1.0f - ( in_bone_weights.x + in_bone_weights.y + in_bone_weights.z );
    mat4 mat =  getBoneMatrix( in_bone_indices.x ) * in_bone_weights.x;
    mat +=      getBoneMatrix( in_bone_indices.y ) * in_bone_weights.y;
    mat +=      getBoneMatrix( in_bone_indices.z ) * in_bone_weights.z;
    mat +=      getBoneMatrix( in_bone_indices.w ) * final_weight;
    

    //mat4 mat = getBoneMatrix( in_bone_indices.x );

    //ex_position = mat * vec4( in_position, 1.0 );
    ex_position = mat * vec4( 0.0, 0.0, 0.0, 1.0 );
    /*
    ex_position = vec4( in_position, 1.0 ) + vec4(
        mat[3][0],
        mat[3][1],
        mat[3][2],
        0.0
        );
    */

    // apply model view matrices
    gl_Position = in_projection * in_model_view * ex_position;
    //gl_Position = in_projection * in_model_view * vec4( in_position, 1.0 );

    ex_normal = vec3( mat * vec4(in_normal, 1.0) );

    ex_texture_coord = in_texture_coord;
}
