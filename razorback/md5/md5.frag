#version 150

// inputs
uniform sampler2D in_diffuse;
in vec4 ex_position;
in vec3 ex_normal;
in vec2 ex_texture_coord;

// outputs
out vec4 out_frag_colour;

void main (void)
{
    vec4 colour = texture( in_diffuse, ex_texture_coord.st );
    out_frag_colour = vec4( colour.rgb, 1.0 );

    out_frag_colour = ex_position / 15.0;
}
