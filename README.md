# Spider OS distribution layer

Spider OS derives from Aurora KDE using the Universal Blue image-template
pattern. The host operating system is atomic and rollback-capable. Spider Core,
the command center, original branding, desktop launchers, and the isolated Kali
Security Lab are added during the image build.

Ubuntu Studio remains the creative-workflow reference for future audio and
media configuration. It is not the image base.

## Build the bootc image

Run this on Aurora, another Universal Blue system, or a Fedora machine with
Podman:

    ./distro/build-image.sh

This produces localhost/spider-os:latest in the root container store and runs
the bootc image lint check.

The default base supports Intel and AMD graphics. If the Dell hardware report
shows a supported NVIDIA GPU, build against Aurora's NVIDIA image instead:

    SPIDER_BASE_IMAGE=ghcr.io/ublue-os/aurora-nvidia-open:stable \
      ./distro/build-image.sh localhost/spider-os:nvidia

Do not choose the NVIDIA variant until the GPU model is known. Older NVIDIA
cards may need a different driver path.

## Build the installer ISO

    ./distro/build-iso.sh

The bootc image builder writes the installer artifacts under output. The
process requires sudo because image assembly needs privileged storage and
mount operations.

Test the image in a virtual machine before installing it on physical hardware.
Daily-driver release requires verified boot, install, encryption, graphics,
Wi-Fi, audio, update, rollback, and recovery paths.

For an unknown Dell desktop, run spider-hardware-report after booting Linux.
The report includes useful tuning information but deliberately omits serial
numbers and service tags.

## Kali Security Lab

On an installed Spider OS system:

    spider-security-lab setup headless
    spider-security-lab enter

Profiles are headless, default, and large. The official Kali rolling image is
used. The lab is a rootless Podman container with no host folders mounted,
limited capabilities, a process limit, and an 8 GiB memory ceiling.

The default headless profile is the practical starting point. The large profile
is substantially larger and should not be the default merely because its name
sounds impressive.

## Publishing

Before public or multi-machine release, place this source into a repository
created from the current Universal Blue image-template, configure its official
build and disk-image workflows, create a Cosign key, store only the private key
as the CI signing secret, commit the public key, and enforce signature
verification on installed systems.
