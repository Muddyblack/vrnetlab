# Convert ISO to KVM-Compatible Image and Boot with QEMU

This guide explains how to convert an ISO file into a KVM-compatible image and set it up for use with QEMU.

## Prerequisites
- A Linux system with `qemu-utils` and `qemu-kvm` installed.
- An ISO file of the operating system you want to install.
- Sufficient disk space for the virtual machine image.

## Step 1: Create a QCOW2 Image
Before installing the OS, create a QCOW2 image file to serve as the virtual machine's disk:

```bash
qemu-img create -f qcow2 genuscreen.qcow2 20G
```

This creates a 20GB virtual disk in QCOW2 format.

## Step 2: Install the OS from ISO
Use QEMU to boot from the ISO and install the operating system:

```bash
qemu-system-x86_64 -m 4096  -cpu host -smp 2 -enable-kvm  -drive file=genuscreen.qcow2,format=qcow2 -cdrom genuscreen.iso -boot d  -serial mon:stdio -nographic
```

### Key Options:
- `-serial mon:stdio` redirects the serial console to your terminal.
- `-nographic` disables graphical output and forces console mode.
- `-boot d` ensures the VM boots from the CD-ROM for installation.

### Console Commands:
- Press `Ctrl+a` then `c` to switch to the QEMU monitor.
- Press `Ctrl+a` then `x` to exit QEMU.
- Use `info qtree` in QEMU monitor to check device configuration.

## Step 3: Boot the Installed System
After installation, start the VM from the disk:

```bash
qemu-system-x86_64 -m 4096 -cpu host -smp 2 -enable-kvm -drive file=genuscreen.qcow2,format=qcow2 -boot c -serial mon:stdio -nographic
```

### Notes:
- `-boot c` ensures the VM boots from the installed disk instead of the ISO.
- The system expects COM1 (ttyS0) as the console.
- Installation logs will be visible on the serial console.

With these steps, your system should be up and running on KVM using QEMU!