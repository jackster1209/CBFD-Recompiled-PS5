# Conker: Recompiled — PS5 port plan

Status: initial source audit and proposed implementation roadmap.
Date: 2026-10-04.
Working branch: `ps5/dev`.
Audited game revision: `5ea55d149eef2ff1ea36718013025c5e67619db9`.
First delivery format: native home-screen title, as selected by the owner.
No PS5 executable has been built or tested in this audit.

## Product goal

A standalone Conker title that feels at home on PS5: controller-only setup, fast repeat launches, dependable saves, clean frame pacing, readable television UI, PlayStation button prompts, and deliberate DualSense feedback. Vulkan is the preferred graphics path. Maintain the game's character and timing while improving presentation.

The first quality target is 1080p SDR output with correct original game timing and a stable 30 fps presentation baseline. Next prove smooth 60 fps presentation using RT64 interpolation; do not describe that as 60 Hz game simulation. Evaluate 1440p/4K rendering and 120 Hz presentation only after measured headroom and visual correctness. Internal render resolution, output resolution, presentation rate, and game update rate are separate settings and metrics.

Homebrew can deliver an excellent native experience. System trophies, Activities, suspend/resume, HDR, VRR, and advanced controller features require separate API and hardware validation. None is promised by this plan.

## Evidence from the current code

These findings are source observations, not console results.

| Area | Current implementation | Port consequence |
| --- | --- | --- |
| Build | `host/CMakeLists.txt` builds C11/C++20, generated `RecompiledFuncs`, recompiled audio RSP code, N64ModernRuntime, RT64 and RecompFrontend. `build.sh` builds generators on the host and applies dependency patches. | Separate host tools from PS5 cross-compilation. Preserve generation hashes and all Conker patches. |
| Game execution | `host/src/main.cpp` registers game, renderer, input and audio callbacks; initializes FR=1, CIC 6105 and TLB mappings. | Keep this game-specific initialization; replace platform services around it. This is a native recompile, not a RetroArch core. |
| Renderer | RT64 plus `recomp/rt64.patch`, including Conker F3DEX2CBFD microcode and framebuffer/interpolation changes. | Port the existing renderer. Replacing it wholesale would discard substantial Conker-specific work. |
| Graphics platform | Pinned Plume defines desktop/mobile `RenderWindow` types, initializes Vulkan with Volk, requests Vulkan 1.2, and creates Win32/SDL/Android/Xlib/Metal surfaces. | Add an explicit PS5 platform path, a static-driver loading adapter, and display WSI. Do not pretend PS5 is Linux. |
| Shader path | RT64 CMake invokes DXC to embed SPIR-V. `rt64_raster_shader.cpp` specializes those modules through re-spirv; the shader-cache DXC compiler is Windows-only. | Keep DXC and shader embedding on the host. Still port re-spirv and test both ubershader and specialized pipelines on RADV. |
| Frontend | `host/src/frontend.cpp` combines SDL initialization/windowing/input with RecompFrontend/RmlUi and native file dialogs. | Introduce a PS5 frontend/platform boundary. Replace desktop file dialogs with controller-driven setup; assess RmlUi reuse after renderer bring-up. |
| Audio | `host/src/audio_output.cpp` queues stereo PCM through SDL. It swaps sample channels from word-swizzled RDRAM and subtracts one 736-frame buffer from queue reporting. | Preserve sample ordering and AI pacing semantics. Use native AudioOut with a bounded ring buffer and resampling where required. |
| Input | SDL controllers, remapping and four-port assignment in `frontend.cpp`; `rumble.cpp` sends SDL joystick rumble. | Native pad/user handling, stable controller assignment, PS prompts and disconnect recovery; bridge the existing N64 input and rumble callbacks. |
| Memory/threading | Runtime `recomp.cpp` uses guarded virtual-memory allocation via mmap/mprotect; `threads.cpp` has Windows/Linux/macOS platform branches. | Audit PS5 reservation/protection semantics, libc++, thread synchronization, TLS, clocks and priority APIs before game bring-up. |
| Saves/data | EEPROM through the runtime; desktop data discovery and executable-relative migration in `main.cpp`. | Explicit PS5 asset and writable-data roots, per-user separation where validated, atomic save handling and backup/recovery. |

### Dependency revisions already pinned by the game

| Dependency | Audited revision |
| --- | --- |
| N64ModernRuntime | `cdf5abbd5026fef5c364c676e4667c45e42b6863` |
| N64Recomp | `ffb39cdad1da5de07eaaa48bd1db4a89a7986771` |
| RT64 | `43373749dac9bbc1b653e6a02aed40a9e1783bed` |
| RecompFrontend | `b1a1477c6556aeb7ed45defbfb5924f721efebc1` |
| Plume (inside RT64) | `d890ac899e505fb30040e037a4037cdeca68f033` |

Mihawk's RetroArch source was reviewed at tree `8854f31c648c918c7208a404cdb546ae2f6eb610`. PS5_Vulkan main resolved to `4271e2e309d9a7eea3a893f5b94427bb78e586ed` during this audit. Choose and record a mutually compatible SDK/Mesa/Vulkan revision set in milestone 0; these observed heads are not yet a validated dependency lock.

### What Mihawk's work establishes

The current PS5_RetroArch README says its native title uses PS5_Vulkan's RADV release archive and link recipe. `src/radv_icd_ps5.c` bridges the driver's ICD entry point to application Vulkan proc lookup. `src/input_ps5.cpp` implements native pad handling and synthesized DualSense haptics using a controller audio port, with ordinary vibration fallback. `src/audio_ps5.cpp` uses native AudioOut at 48 kHz with a worker and bounded buffering.

PS5_Vulkan documents a Mesa RADV PS5 winsys, VideoOut presentation through `VK_KHR_display`, and application/CTS evidence. Its advertised API version is not proof of RT64 compatibility or formal Khronos conformance. For our title, verify the exact extensions, features, formats, memory types and synchronization operations actually used by RT64/Plume.

Recommendation: use the RADV route first. The older ps5vk implementation is a possible diagnostic alternative, not an assumed compatible fallback for Plume's Vulkan 1.2 setup.

## Proposed architecture

Retain recompiled game functions, RSP audio, N64 runtime behavior, Conker hooks and RT64's rendering algorithms. Add PS5 services at well-defined seams.

Proposed directories, to be created during implementation:

- `host/platform/ps5/`: title entry/lifecycle, paths, native pad, audio, logging and capability reporting.
- `cmake/toolchains/ps5.cmake`: target toolchain; separate host-build directory for N64Recomp/RSPRecomp/DXC/file-to-C tools.
- `platform/ps5/`: packaging metadata, generated title layout and pinned import/tooling configuration.
- `docs/ps5/`: compatibility table, capability audit and repeatable console test recipes.
- `evidence/ps5/`: sanitized run summaries, build IDs and referenced captures.

Keep the desktop build working. Use explicit PS5 build options rather than scattered Linux defines. Maintain platform changes to RT64, Plume and runtime as reproducible patches or pinned forks; never depend on untracked edits inside submodules.

Preferred graphics chain: Conker display lists → patched RT64 → Plume PS5 backend → PS5 RADV → VideoOut. Use the driver's display WSI to own presentation; avoid opening a competing VideoOut backend for game frames.

First inspect SDK-provided C/C++ runtime facilities and native-title imports before borrowing RetroArch shims. Its libretro-specific plumbing is not automatically appropriate here. Retain attribution and compatible source/license notices for any reused platform or packaging code. Keep ROMs, extracted assets and generated game data out of version control and CI artifacts.

## Milestones and acceptance gates

Advance on demonstrated results. Effort ranges are provisional focused engineering days, exclude waiting for console tests, and will be revised after milestone 2. They are not delivery dates.

| Milestone | Visible result | Acceptance gate | Rough effort |
| --- | --- | --- | --- |
| 0 — Reproducible baseline | Desktop baseline and documented PS5 target | Owner-provided US ROM builds locally; record representative scenes and known bugs. Pin toolchain/SDK/driver dependencies; capture firmware, loader and display details. | 2–4 days |
| 1 — Native title shell | Conker tile launches a diagnostic screen on PS5 | Three cold launches; pad navigation, native audio test, writable-file round trip and clean exit. Embed build ID; preserve useful logs after failure. | 3–7 days |
| 2 — Vulkan and RT64 proof | Actual RT64 output on the console | RADV triangle/texture/compute/depth/readback probes, then RT64 render-context and representative shader pipelines. Test ubershader and specialization, image formats, descriptor behavior, VMA allocation and swapchain acquisition/present. Correct output for 10 minutes. | 5–15 days |
| 3 — First playable slice | Intro → menu → controllable gameplay with sound | Real controller input and original timing; synchronized music/voices; EEPROM survives exit/relaunch; one continuous 30-minute session. | 5–15 days |
| 4 — Gameplay alpha | Representative campaign and local multiplayer | Chapter progression tests; four-player splitscreen where hardware allows; 2-hour soak; no unexplained hangs or save loss. Track regressions against desktop captures. | 10–20 days |
| 5 — Performance beta | Smooth default preset and quality options | Measured 60 fps presentation where interpolation is correct, with 30 fps option; original game speed; frame-time/memory/audio reports. Qualify higher resolutions and optional 120 Hz individually. | 5–15 days |
| 6 — PS5 experience | Controller-first UI and purposeful DualSense feedback | ROM setup, menus, errors and settings usable from the couch; remapping, PS prompts, disconnect recovery, reliable save UX; baseline rumble plus optional native haptics. | 5–15 days |
| 7 — Release candidate | Installable, maintainable native title | Campaign completion on PS5; repeated launch/exit and supported lifecycle tests; upgrade preserves saves/settings; documented compatibility, recovery and licenses. Hardware-tested feature matrix. | 5–10 days plus playthrough |

The greatest schedule risk is milestone 2, followed by target C++ runtime/memory compatibility. If the graphics gate fails, report the exact failing operation and a minimal reproducer before deciding whether to adapt Plume, fix the driver, or reduce optional renderer capabilities.

### Milestone details

**0: baseline and feasibility.** Reproduce the existing game before changing platform code. Separate documented source behavior from what the owner actually observes on the desktop GPU. Audit generated-code tool execution during cross-builds, target libraries, runtime mod dependencies and virtual-memory reservation requirements. Identify which mod initialization paths must be gated for an initial no-mod build. The base recompile is ahead-of-time, but optional .nrm mod/hook machinery needs its own executable-memory audit.

**1: title shell.** Prove packaging and platform APIs independently of Conker. Use a unique project title identity; distinguish executable assets from writable data. Exercise libc++ exceptions, filesystem, TLS, mutexes, condition variables and threads. A payload smoke test may help diagnose the native title, but home-screen launch remains the delivery target.

**2: graphics.** Port Plume's RenderWindow type, instance extension list, Volk initialization, surface creation, size/refresh queries and present-mode selection. Prefer static proc initialization against RADV. Probe actual display modes and fall back to supported FIFO modes; do not assume desktop immediate present, display-timing or present-wait extensions. Qualify raster and compute first; ray tracing is outside the initial scope. Validate cold/warm shader caches, memory pressure and GPU readbacks. Black screens need logged Vulkan results and a bounded diagnostic path rather than silent infinite waits.

**3: game slice.** A diagnostic headless game run can verify scheduling before graphics integration. Preserve FR/CIC/TLB and Conker microcode changes. Bridge native input to runtime callbacks. Maintain the AI queue-length contract in game-rate frames even when AudioOut consumes 48 kHz audio. Test both channels, silence, frequency changes and pause/resume buffering.

**4: correctness.** Include intro/cutscenes, shadows, framebuffer effects, pause blur, reflective surfaces, camera cuts, boss transitions, water and splitscreen. Test save slots, reset, relaunch and controller ordering. Keep upstream defects and PS5 regressions in separate columns.

**5: optimization.** Record median/p95/p99 frame times, worst stalls, CPU/GPU timings where available, queue depth, audio underruns, peak memory and load times. Aim for 16.67 ms presentation intervals at 60 Hz; quantify exceptions rather than judging an FPS counter alone. Respect the shared CPU/GPU memory budget. Tune worker counts and pipeline warming from measurements. Do not inflate game simulation speed to chase 60/120 fps.

**6: feel.** Auto-start after successful first-time setup; keep settings accessible without a desktop launcher. Provide UI scale/safe-area options, sensible default controls, analog dead zones, subtitles/settings inherited from the game where applicable, and haptic intensity/off controls. Map ordinary N64 rumble first. Add richer effects from semantic game events only when hooks reliably identify those events; blanket vibration is not a premium feature.

**7: release.** Declare supported firmware/loader/display combinations from actual runs. Handle upgrade, missing ROM, corrupt settings, failed writes and interrupted saves. Perform lifecycle tests supported by the environment; do not claim full rest-mode resume until it works with GPU/audio state restored.

## PS5 feature priorities

| Feature | Priority | Implementation/validation condition |
| --- | --- | --- |
| Native title tile and couch-friendly setup | Required | Native-title packaging plus controller-only UI; no keyboard dependence. |
| PlayStation prompts, remapping and analog tuning | Required | All menu and gameplay paths, including multiplayer/controller changes. |
| Native audio and dependable saves | Required | Audio pacing, graceful drain, atomic writes and persistent data across upgrades. |
| Baseline rumble → DualSense haptics | High | Native vibration first; synthesized haptic path has external source precedent, physical feel requires owner testing. |
| Adaptive triggers | Research after alpha | Confirm native API/ABI and supported firmware; semantic weapon/action hooks; disable and fallback options. |
| Gyro aiming and touchpad shortcuts | Optional after alpha | Confirm sensor/touch reporting; calibration, opt-in behavior and sensible mappings. |
| Controller speaker and light bar | Optional | API proof, volume/disable controls, restraint and measurable benefit. |
| 4K render and 120 Hz output | Stretch | Supported modes, frame-time headroom and interpolation correctness; retain dependable lower-cost presets. |
| HDR and VRR | Research | Driver/VideoOut support, title metadata and display behavior must all be proven. |
| 3D audio/Tempest | Research | Stereo output alone does not create spatial sound; requires meaningful positional source access and a usable native path. |
| Achievements | Optional | Local persistent achievements and polished in-game notifications are attainable design targets; OS trophy integration requires a separate proof. |
| System trophies, Activities, capture integration, full rest-mode resume | Uncommitted | Validate each capability independently; no assumption of retail SDK privileges or system-service availability. |

## Known upstream issues affecting the polish bar

The audited README reports the game has been completed upstream, but documents:
- Widescreen pause blur cropping.
- Missing reflection textures on environment-mapped surfaces.
- Character snapping and camera blending across cuts above 30 fps.
- Limited real-GPU Linux validation.

These are not verified PS5 defects. Record them in milestone 0 and prioritize interpolation/camera fixes before making a 60 fps mode the default. An impressive resolution label will not compensate for visibly broken rendering.

## Next implementation batch

1. Record owner's firmware, homebrew enabler/title loader, display modes, and available test machine.
2. Build a local desktop baseline using the owner's ROM and lock a coherent PS5 dependency set.
3. Add the PS5 toolchain/host-tool separation and native diagnostic title.
4. Create a small Vulkan capability/reporting executable and the Plume PS5 integration patch.
5. Stop the batch at the first reproducible RT64 frame; collect console evidence before expanding gameplay scope.

No live console access or ROM was supplied in this session. Compilation and hardware claims therefore remain pending.

## Source references

Game links use the audited revision; dependency links use their pinned revisions.

- [Game host build](https://github.com/jackster1209/CBFD-Recompiled-PS5/blob/5ea55d149eef2ff1ea36718013025c5e67619db9/host/CMakeLists.txt)
- [Game entry and runtime callbacks](https://github.com/jackster1209/CBFD-Recompiled-PS5/blob/5ea55d149eef2ff1ea36718013025c5e67619db9/host/src/main.cpp)
- [Desktop frontend](https://github.com/jackster1209/CBFD-Recompiled-PS5/blob/5ea55d149eef2ff1ea36718013025c5e67619db9/host/src/frontend.cpp)
- [Audio pacing](https://github.com/jackster1209/CBFD-Recompiled-PS5/blob/5ea55d149eef2ff1ea36718013025c5e67619db9/host/src/audio_output.cpp)
- [Conker RT64 changes](https://github.com/jackster1209/CBFD-Recompiled-PS5/blob/5ea55d149eef2ff1ea36718013025c5e67619db9/recomp/rt64.patch)
- [Upstream status and defects](https://github.com/jackster1209/CBFD-Recompiled-PS5/blob/5ea55d149eef2ff1ea36718013025c5e67619db9/README.md)
- [RT64 shader specialization](https://github.com/rt64/rt64/blob/43373749dac9bbc1b653e6a02aed40a9e1783bed/src/render/rt64_raster_shader.cpp)
- [Plume Vulkan backend](https://github.com/renderbag/plume/blob/d890ac899e505fb30040e037a4037cdeca68f033/plume_vulkan.cpp)
- [Runtime allocation](https://github.com/N64Recomp/N64ModernRuntime/blob/cdf5abbd5026fef5c364c676e4667c45e42b6863/librecomp/src/recomp.cpp)
- [Mihawk native title and dependency recipe](https://github.com/mihawk-99/PS5_RetroArch/blob/8854f31c648c918c7208a404cdb546ae2f6eb610/README.md)
- [Mihawk native input/haptics](https://github.com/mihawk-99/PS5_RetroArch/blob/8854f31c648c918c7208a404cdb546ae2f6eb610/src/input_ps5.cpp)
- [Mihawk native audio](https://github.com/mihawk-99/PS5_RetroArch/blob/8854f31c648c918c7208a404cdb546ae2f6eb610/src/audio_ps5.cpp)
- [PS5 Vulkan/RADV architecture](https://github.com/mihawk-99/PS5_Vulkan/blob/4271e2e309d9a7eea3a893f5b94427bb78e586ed/README.md)
