#version 150

// inputs
uniform mat4 in_model_view;
uniform mat4 in_projection;

in vec3 in_normal;
in vec2 in_texture_coord;
//in uvec4 in_bone_indices;
in vec4 in_bone_indices;
in vec4 in_bone_weights_1;
in vec4 in_bone_weights_2;
in vec4 in_bone_weights_3;
in vec4 in_bone_weights_4;

uniform samplerBuffer in_bone_matrices;

// outputs
out vec4 ex_position;
out vec3 ex_normal;
out vec2 ex_texture_coord;

mat4 construct_matrix( samplerBuffer sampler, int weight_index )
{
    mat4 matrix = mat4(
        texelFetch( sampler, (weight_index * 4) + 0 ),
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

float compute_w( vec3 quat )
{
    // extract our W quaternion component
    float w = 1.0 - pow(quat.x, 2) - pow(quat.y, 2) - pow(quat.z, 2);
    if ( w < 0.0 )
        w = 0.0;
    else
        w = sqrt( w );
    return w;
}

vec4 get_bone_quaternion( int weight_index )
{
    /*
    mat4 bone_mat = construct_matrix( in_bone_matrices, weight_index );
    return bone_mat[ 1 ];
    */
    vec4 quat = texelFetch( in_bone_matrices, (weight_index * 2) + 0 );
    //quat.w = compute_w( quat.xyz );
    return quat;
}

vec3 get_bone_position( int weight_index )
{
    /*
    mat4 bone_mat = construct_matrix( in_bone_matrices, weight_index );
    return bone_mat[ 0 ].xyz;
    */
    //return texelFetch( in_bone_matrices, (weight_index * 2) + 1 ).xyz;
    return texelFetch( in_bone_matrices, (weight_index * 2) + 1 ).xyz;
}

mat4 get_weight_matrix()
{
    return mat4(
        in_bone_weights_1,
        in_bone_weights_2,
        in_bone_weights_3,
        in_bone_weights_4
        );
}

vec3 get_weight_position( int weight_index )
{
    mat4 weights = get_weight_matrix();
    return weights[ weight_index ].xyz;
}

float get_weight_bias( int weight_index )
{
    mat4 weights = get_weight_matrix();
    return weights[ weight_index ].w;
}


vec3 rotate_vector( vec4 quat, vec3 vec )
{
    return vec + 2.0 * cross(cross(vec, quat.xyz ) + quat.w * vec, quat.xyz);
}

/*
vec3 rotate_vector( vec4 quat, vec3 vec )
{
    vec3 temp = cross(quat.xyz, vec) + quat.w * vec;
    vec3 rotated = (cross(temp, -quat.xyz) + dot(quat.xyz, vec) * quat.xyz + quat.w * temp);
    return rotated;
}
*/
/*
vec3 rotate_vector(vec4  j, vec3 w)
{
    float dp = -dot(j.xyz, w);
    vec3 conj = -1.0 * j.xyz;
    vec3 intVec = (j.w * w) + cross(j.xyz, w);

    return (j.w * intVec) + (dp * conj) + cross(intVec, conj);
}
*/

int get_bone_index( int index )
{
    return int( in_bone_indices[ index ] );
}


void main()
{
    // get the bone matrices
    /*
    mat4 bone1 = get_bone_matrix( get_bone_index( 0 ) );
    mat4 bone2 = get_bone_matrix( get_bone_index( 1 ) );
    mat4 bone3 = get_bone_matrix( get_bone_index( 2 ) );
    mat4 bone4 = get_bone_matrix( get_bone_index( 3 ) );
    */
    /**/
    vec4 bone_quat1 = get_bone_quaternion( get_bone_index( 0 ) );
    vec4 bone_quat2 = get_bone_quaternion( get_bone_index( 1 ) );
    vec4 bone_quat3 = get_bone_quaternion( get_bone_index( 2 ) );
    vec4 bone_quat4 = get_bone_quaternion( get_bone_index( 3 ) );
    /**/

    vec3 bone_pos1 = get_bone_position( get_bone_index( 0 ) );
    vec3 bone_pos2 = get_bone_position( get_bone_index( 1 ) );
    vec3 bone_pos3 = get_bone_position( get_bone_index( 2 ) );
    vec3 bone_pos4 = get_bone_position( get_bone_index( 3 ) );

    vec3 weight_pos1 = get_weight_position( 0 );
    vec3 weight_pos2 = get_weight_position( 1 );
    vec3 weight_pos3 = get_weight_position( 2 );
    vec3 weight_pos4 = get_weight_position( 3 );

    // get the bone weights
    // ensure all weights add up to 1.0
    float weight_bias1 = get_weight_bias( 0 );
    float weight_bias2 = get_weight_bias( 1 );
    float weight_bias3 = get_weight_bias( 2 );
    float weight_bias4 = get_weight_bias( 3 );
    //float weight4 = 1.0f - weight1 - weight2 - weight3;

    // get our vertex positions
    // rotate each by the appropriate bone
    /**/
    vec3 pos1 = bone_pos1 + rotate_vector( bone_quat1, weight_pos1 );
    vec3 pos2 = bone_pos2 + rotate_vector( bone_quat2, weight_pos2 );
    vec3 pos3 = bone_pos3 + rotate_vector( bone_quat3, weight_pos3 );
    vec3 pos4 = bone_pos4 + rotate_vector( bone_quat4, weight_pos4 );
    /**/
    /*
    vec3 pos1 = ( bone1 * vec4(weight_pos1, 1.0) ).xyz;
    vec3 pos2 = ( bone2 * vec4(weight_pos2, 1.0) ).xyz;
    vec3 pos3 = ( bone3 * vec4(weight_pos3, 1.0) ).xyz;
    vec3 pos4 = ( bone4 * vec4(weight_pos4, 1.0) ).xyz;
    */

    // sum the positions applied by the weights
    ex_position = vec4(
        (pos1 * weight_bias1) +
        (pos2 * weight_bias2) +
        (pos3 * weight_bias3) +
        (pos4 * weight_bias4),
        1.0
        );
    //ex_position = vec4( pos1, 1.0);

    // apply model view matrices
    gl_Position = in_projection * in_model_view * ex_position;

    //ex_normal = vec3( mat * vec4(in_normal, 0.0) );

    ex_texture_coord = in_texture_coord;
}
