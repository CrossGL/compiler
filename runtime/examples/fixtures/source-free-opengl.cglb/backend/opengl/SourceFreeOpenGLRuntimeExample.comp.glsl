// Generated OpenGL GLSL artifact for the runtime loader boundary example.
#version 450

layout(local_size_x = 1, local_size_y = 1, local_size_z = 1) in;

layout(std430, binding = 0) buffer OutputBufferBlock {
  vec4 OutputBuffer[];
};

void source_free_opengl_main() {
  OutputBuffer[gl_GlobalInvocationID.x] = vec4(0.0, 0.25, 1.0, 1.0);
}
