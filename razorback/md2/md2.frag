#version 150

// inputs
uniform sampler2DRect tex0;
in vec3 ex_normal;
in vec2 ex_texture_coord;

// outputs
out vec4 fragColor;

void main (void)
{
    vec4 colour = texture( tex0, ex_texture_coord.st ) + vec4( 0.1, 0.1, 0.1, 0.0 );
	fragColor = vec4( colour.rgb, 1.0 );
}
