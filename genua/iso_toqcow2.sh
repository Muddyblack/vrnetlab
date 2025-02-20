#!/bin/bash

ISO_FILE=$1

if [ -z "$ISO_FILE" ]; then
    echo "Usage: $0 <iso_file> [config_file]"
    echo "Example: $0 genua.iso config.yml"
    exit 1
fi

# Derive QCOW2 file name from ISO file
QCOW2_FILE="${ISO_FILE%.*}.qcow2"

# Remove QCOW2 file if it already exists
if [ -f "$QCOW2_FILE" ]; then
    rm -f "$QCOW2_FILE"
fi

CONFIG_FILE=${2:-"config.yml"}

# Install expect if not present
if ! command -v expect &> /dev/null; then
    echo "Installing expect..."
    apt-get update && apt-get install -y expect
fi

# Create QCOW2 disk
qemu-img create -f qcow2 "$QCOW2_FILE" 20G

# Load config values or use defaults
if [ -f "$CONFIG_FILE" ]; then
    source <(sed 's/:[^:\/\/]/=/g' "$CONFIG_FILE")
fi

KEYBOARD=${keyboard:-"us"}
HOSTNAME=${hostname:-"genuscreen"}
ADDRESS=${address:-"192.168.1.10"}
NETMASK=${netmask:-"24"}
GATEWAY=${gateway:-"192.168.1.1"}
PASSWORD=${password:-"!Gclab@screen2025"}
ENABLE_SSH=${enable_ssh:-"yes"}
RESTRICT_WEB=${restrict_web:-"no"}
ADMIN_ACL=${admin_acl:-"192.168.1.0"}
ADMIN_ACL_MASK=${admin_acl_mask:-"24"}

# Create expect script
cat > install.exp << 'EOF'
#!/usr/bin/expect -f

set keyboard [lindex $argv 0]
set hostname [lindex $argv 1]
set address [lindex $argv 2]
set netmask [lindex $argv 3]
set gateway [lindex $argv 4]
set password [lindex $argv 5]
set enable_ssh [lindex $argv 6]
set restrict_web [lindex $argv 7]
set admin_acl [lindex $argv 8]
set admin_acl_mask [lindex $argv 9]

set timeout 300
set force_conservative 0
if {$force_conservative} {
    set send_slow {1 .1}
    proc send {ignore arg} {
        sleep .1
        exp_send -s -- $arg
    }
}

spawn qemu-system-x86_64 \
    -name genua-install \
    -machine q35 \
    -cpu host \
    -enable-kvm \
    -m 4096 \
    -nographic \
    -serial mon:stdio \
    -drive if=virtio,file=QCOW2_FILE,format=qcow2 \
    -cdrom ISO_FILE \
    -boot d \
    -device virtio-net-pci,netdev=mgmt \
    -netdev user,id=mgmt

# Initial installation prompts
expect {
    -re "proceed.*\\\[.*n.*\\\]" {
        send "yes\r"
    }
    timeout {
        puts "Timeout waiting for initial prompt"
        exit 1
    }
}

expect {
    -re "32-bit appliance.*\\\[.*n.*\\\]" {
        send "no\r"
    }
}

expect {
    "Keyboard mapping" {
        send "$keyboard\r"
    }
}

expect "Fully Qualified Domain Name?"
send "$hostname\r"

expect "Which interface"
send "\r"

expect "Address?"
send "$address\r"

expect "Netmask length"
send "$netmask\r"

expect "Media"
send "\r"

expect "Default gateway/router"
send "$gateway\r"

# Password prompts
expect "New password:"
send "$password\r"
expect "Retype new password:"
send "$password\r"

expect "Enable SSH daemon"
send "$enable_ssh\r"

expect "Restrict access to Web-GUI"
send "$restrict_web\r"

if {"$restrict_web" == "yes"} {
    expect "Admin-ACL network"
    send "$admin_acl\r"
    expect "Admin-ACL netmask length"
    send "$admin_acl_mask\r"
}

expect "Save configuration to disk"
send "yes\r"

expect "wait for more?"
send "no\r"

# Wait for completion
expect "login:"
send "\x01x"

EOF

# Replace placeholders in expect script
sed -i "s|QCOW2_FILE|$QCOW2_FILE|g" install.exp
sed -i "s|ISO_FILE|$ISO_FILE|g" install.exp

# Make expect script executable
chmod +x install.exp

# Run installation
./install.exp "$KEYBOARD" "$HOSTNAME" "$ADDRESS" "$NETMASK" "$GATEWAY" "$PASSWORD" \
    "$ENABLE_SSH" "$RESTRICT_WEB" "$ADMIN_ACL" "$ADMIN_ACL_MASK"

# Cleanup
rm install.exp

echo "Installation complete. QCOW2 image is ready at $QCOW2_FILE"
