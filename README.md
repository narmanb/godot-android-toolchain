# Godot Android Toolchain

Reusable, reproducible tooling for validating and provisioning a Godot 4.7.2 Android build environment.

This repository is a **generic developer tool project**. Its CI validates and packages only the toolchain itself; it does not contain or build unrelated private game repositories.

## Pinned toolchain

- Godot: 4.7.2 stable
- Godot Linux editor SHA-256: `cadd3204e728a35d3f13adb7fd0d7902636b79f6b95c40c265eb73b6c35329e4`
- Godot export templates SHA-256: `f298490b8d44d934be425a5a65a51bf15f422428b229a06a6e11d9ffea248011`
- Java: 21

The workflow downloads the official Godot release files, verifies their hashes, installs the Android SDK/build tools needed for Android export, runs a tiny canary Godot project through a clean import/export, validates the APK, and publishes the resulting generic local-build bundle as a workflow artifact.

## Intended use

Download the generated toolchain artifact and use it as a local build environment for Godot projects. Project source stays in its own repository/environment and is never copied into this public toolchain repository.
