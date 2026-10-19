#version 150

in vec3 Position;
out vec2 vUV;

void main() {
    vUV = Position.xy;
    gl_Position = vec4(Position.xy, 0.9999, 1.0);
}
