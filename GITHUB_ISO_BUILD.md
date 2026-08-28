# GitHub ISO build

Spider OS can build its bootable installer on a GitHub-hosted Linux runner.

## Automatic path

The workflow at `.github/workflows/build-spider-os-iso.yml`:

1. validates the Python and shell source,
2. builds the Spider OS bootc container from Aurora,
3. runs bootc-image-builder to create an installer ISO,
4. renames the result to `Spider_OS_x86_64.iso`,
5. writes a SHA-256 checksum, and
6. uploads both files as the `Spider-OS-ISO` Actions artifact.

The workflow may be started manually from **Actions > Build Spider OS ISO > Run workflow**. It also runs when relevant system files are pushed to `main`.

## Safety

Treat the first ISO as an engineering build. Test it in a VM first, then boot it from USB on the target Dell without installing. Verify graphics, network, audio, input devices, storage detection, The Web, and Webbie before installation to internal storage.
