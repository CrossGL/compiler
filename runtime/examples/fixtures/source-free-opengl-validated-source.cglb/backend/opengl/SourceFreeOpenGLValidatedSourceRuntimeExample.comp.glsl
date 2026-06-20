// Generated OpenGL GLSL backendSource artifact for validated source fixture.
#version 450

layout(local_size_x = 1, local_size_y = 1, local_size_z = 1) in;

layout(std430, binding = 0) buffer OutputBufferBlock {
  vec4 OutputBuffer[];
};

void source_free_opengl_validated_source_main() {
  OutputBuffer[gl_GlobalInvocationID.x] = vec4(0.125, 0.375, 0.875, 1.0);
}
