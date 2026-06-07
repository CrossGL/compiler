<div style="display: block;" align="center">
    <img class="only-dark" width="10%" height="10%" src="https://github.com/CrossGL/crossgl-docs/blob/main/docs/assets/logo.png#gh-dark-mode-only"/>
</div>

---

<div style="display: block;" align="center">
    <img class="dark-light" width="5%" >
    <a href="https://crossgl.net/">
        <img class="dark-light" height="5%" width="5%" src="https://github.com/CrossGL/crossgl-docs/blob/main/docs/assets/web_icon.png">
    </a>
    <img class="dark-light" width="5%" >
    <a href="https://docs.crossgl.net">
        <img class="dark-light" height="5%" width="5%" src="https://github.com/CrossGL/crossgl-docs/blob/main/docs/assets/docs.png">
    </a>
    <img class="dark-light" width="5%" >
    <a href="https://github.com/CrossGL/demos">
        <img class="dark-light" height="5%" width="5%" src="https://github.com/CrossGL/crossgl-docs/blob/main/docs/assets/written.png">
    </a>
    <img class="dark-light" width="5%" >
    <a href="https://docs.crossgl.net/products/crossgl-translator/architecture.html">
        <img class="dark-light" height="5%" width="5%" src="https://github.com/CrossGL/crossgl-docs/blob/main/docs/assets/strategic-plan.png">
    </a>
</div>

<br>

<div style="margin-top: 10px; margin-bottom: 10px; display: block;" align="center">
    <a href="https://github.com/CrossGL/compiler/issues">
        <img class="dark-light" style="padding-right: 4px; padding-bottom: 4px;" src="https://img.shields.io/github/issues/CrossGL/compiler">
    </a>
    <a href="https://github.com/CrossGL/compiler/network/members">
        <img class="dark-light" style="padding-right: 4px; padding-bottom: 4px;" src="https://img.shields.io/github/forks/CrossGL/compiler">
    </a>
    <a href="https://github.com/CrossGL/compiler/stargazers">
        <img class="dark-light" style="padding-right: 4px; padding-bottom: 4px;" src="https://img.shields.io/github/stars/CrossGL/compiler">
    </a>
    <a href="https://github.com/CrossGL/compiler/pulls">
        <img class="dark-light" style="padding-right: 4px; padding-bottom: 4px;" src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg">
    </a>
    <a href="https://discord.com/invite/uyRQKXhcyW">
        <img class="dark-light" style="padding-right: 4px; padding-bottom: 4px;" src="https://img.shields.io/discord/1240998239206113330?color=blue&label=%20&logo=discord&logoColor=white">
    </a>
</div>
<br clear="all" />

# CrossGL Compiler

The native ahead-of-time compiler for CrossGL. It takes `.cgl` shader sources through lexing, parsing, type-checked HIR construction, optimization, and target-specific code generation to produce GPU-ready artifacts for Metal, Vulkan (SPIR-V), DirectX (HLSL/DXIL), and OpenGL (GLSL).

## Supported Targets

| Target | Output | Status |
|--------|--------|--------|
| Metal | MSL source / `.metallib` | Active |
| Vulkan | SPIR-V assembly / binary | Active |
| DirectX | HLSL source / DXIL | Active |
| OpenGL | GLSL source | Active |

## Pipeline

```
.cgl source
  → Lexer (tokenization)
  → Parser (AST)
  → HIR construction (typed, resource-annotated)
  → Optimization passes (constant folding, algebraic simplification)
  → Target legalization
  → Backend code generation
  → Package (.cglb)
```

## Building

Requires C++20, CMake 3.20+, and Ninja.

```bash
cmake -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build
```

## CLI Usage

```bash
# Check a shader for diagnostics
cglc check shader.cgl

# Compile to a target
cglc build shader.cgl --target metal
cglc build shader.cgl --target vulkan
cglc build shader.cgl --target directx
cglc build shader.cgl --target opengl

# Dump typed HIR
cglc dump-ir shader.cgl

# List available targets and their capabilities
cglc targets

# Explain target selection for a shader
cglc explain-targets shader.cgl

# Inspect a compiled package
cglc inspect shader.cglb

# Run environment diagnostics
cglc doctor
```

## Example

```cgl
shader SimpleShader {
    struct VertexInput {
        vec3 position;
        vec2 texCoord;
    }

    struct VertexOutput {
        vec2 uv;
        vec4 position;
    }

    struct FragmentInput {
        vec2 uv;
    }

    struct FragmentOutput {
        vec4 color;
    }

    vertex {
        VertexOutput main(VertexInput input) {
            VertexOutput output;
            output.uv = input.texCoord;
            output.position = vec4(input.position, 1.0);
            return output;
        }
    }

    fragment {
        FragmentOutput main(FragmentInput input) {
            FragmentOutput output;
            float r = input.uv.x;
            float g = input.uv.y;
            float b = 0.5;
            output.color = vec4(r, g, b, 1.0);
            return output;
        }
    }
}
```

## Testing

```bash
cmake --build build --target test
```

Tests cover the full pipeline: lexer, parser, HIR semantics, backend code generation, native build validation (Metal/Vulkan), package integrity, and JSON schema conformance.

## Project Structure

```
src/
  Frontend/     Lexer and parser
  HIR/          Typed high-level IR, constant folding, type semantics
  Optimizer/    HIR pass manager
  Backend/      Metal, Vulkan, DirectX, OpenGL code generators
  IR/           IR printer
  Driver/       CLI driver, package tooling, reflection
include/        Public headers
runtime/        Package reader prototype (Python)
tests/          Unit tests, fixtures, schema validation
tools/          CI and schema validation scripts
cmake/          Build system modules
```

## Related Projects

- [CrossGL Translator](https://github.com/CrossGL/crosstl) — Python-based bidirectional shader translator
- [CrossGL Documentation](https://docs.crossgl.net/) — Language reference and guides

<a href="https://github.com/CrossGL/compiler/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=CrossGL/compiler" />
</a>

# Community

- [Twitter](https://x.com/crossGL_)
- [LinkedIn](https://www.linkedin.com/company/crossgl/?viewAsMember=true)
- [Discord](https://discord.com/invite/uyRQKXhcyW)
- [YouTube](https://www.youtube.com/channel/UCxv7_flRCHp7p0fjMxVSuVQ)

## License

CrossGL Compiler is open-source and licensed under the [Apache License 2.0](https://github.com/CrossGL/compiler/blob/main/LICENSE).

---

The CrossGL Team
