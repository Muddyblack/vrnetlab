#!/usr/bin/env python3

import datetime
import logging
import os
import re
import signal
import sys
import subprocess
import yaml

import vrnetlab

def handle_SIGCHLD(signal, frame):
    os.waitpid(-1, os.WNOHANG)

def handle_SIGTERM(signal, frame):
    sys.exit(0)

signal.signal(signal.SIGINT, handle_SIGTERM)
signal.signal(signal.SIGTERM, handle_SIGCHLD)

TRACE_LEVEL_NUM = 9
logging.addLevelName(TRACE_LEVEL_NUM, "TRACE")

def trace(self, message, *args, **kws):
    if self.isEnabledFor(TRACE_LEVEL_NUM):
        self._log(TRACE_LEVEL_NUM, message, args, **kws)

logging.Logger.trace = trace

class GENUSCREEN_vm(vrnetlab.VM):
    def __init__(self, hostname, username, password):
        disk_image = None
        
        # First try the hdd.qcow2 from installer
        if os.path.exists('/hdd.qcow2'):
            disk_image = '/hdd.qcow2'
        else:
            # Fallback to looking for other qcow2 files
            for e in os.listdir("/"):
                if re.search(".qcow2$", e):
                    disk_image = "/" + e
                    break
                    
        if not disk_image:
            raise RuntimeError("No qcow2 disk image found!")

        super(GENUSCREEN_vm, self).__init__(
            username, 
            password, 
            disk_image=disk_image,
            use_scrapli=True, min_dp_nics=1, mgmt_passthrough=True,
            ram=4096
        )
        
        self.hostname = hostname
        self.num_nics = 1
        self.nic_type = "virtio-net-pci"
        self.conn_mode = "tc"
        self.wait_pattern = ">>"

    def bootstrap_spin(self):
        """This function should be called periodically to do work."""
        if self.spins > 600:
            # too many spins with no result ->  give up
            self.logger.debug(
                "node is failing to boot or we can't catch the right prompt. Restarting..."
            )
            self.stop()
            self.start()
            return

        (ridx, match, res) = self.con_expect([b"starting services:"])
        if match:
            # System is booted, wait a moment for services to start
            self.logger.debug("System booted, waiting for services...")
            import time
            time.sleep(2)
            
            self.bootstrap_config()
            
            self.scrapli_tn.close()
            startup_time = datetime.datetime.now() - self.start_time
            self.logger.info("Startup complete in: %s", startup_time)
            self.running = True
            return
        elif res:
            self.write_to_stdout(res)

        return

    def bootstrap_config(self):
        # First do the login sequence without any logging in between
        self.wait_write(self.username, "login:")  # Send username at login prompt
        self.wait_write(self.password, "Password:")  # Send password at password prompt

        # Get management interface config ready
        v4_mgmt_address = vrnetlab.cidr_to_ddn(self.mgmt_address_ipv4)
        
        # configure
        self.wait_write("mode static")
        self.wait_write(f"ipaddress {v4_mgmt_address[0]}")
        self.wait_write(f"netmask {v4_mgmt_address[1]}")
        self.wait_write(f"gwaddress {self.mgmt_gw_ipv4}")
        self.wait_write("activate")

        self.con_read_until(">>")

class GENUSCREEN_INSTALLER(vrnetlab.VM):
    def __init__(self):
        self.iso_file = None
        for f in os.listdir('/'):
            if f.endswith('.iso'):
                self.iso_file = '/' + f
                break
        if not self.iso_file:
            raise RuntimeError("No ISO file found in root directory")
            
        self.qcow2_file = '/hdd.qcow2'
        # Create qcow2 disk early if not already there.
        if not os.path.exists(self.qcow2_file):
            subprocess.run(['qemu-img', 'create', '-f', 'qcow2', self.qcow2_file, '20G'], check=True)
            
        self.config = self._load_config()
        
        # Set required attributes to avoid parent's overlay calls issues.
        self.num_nics = 1
        self.nic_type = "virtio-net-pci"
        self.conn_mode = "tc"
        self.wait_pattern = ">>"
        
        # Now pass a valid disk_image (qcow2 file) to the parent.
        super(GENUSCREEN_INSTALLER, self).__init__(
            username=self.config.get('username', 'root'),
            password=self.config.get('password', '!Gclab@screen2025'),
            disk_image=self.qcow2_file,
            ram=4096,
            use_scrapli=True
        )
        
    def _load_config(self):
        default_config = {
            'keyboard': 'us',
            'hostname': 'genuscreen',
            'address': '192.168.1.10',
            'netmask': '24',
            'gateway': '192.168.1.1',
            'password': '!Gclab@screen2025',
            'enable_ssh': 'yes',
            'restrict_web': 'no',
            'admin_acl': '192.168.1.0',
            'admin_acl_mask': '24'
        }
        
        config_file = '/config/config.yml'
        if os.path.exists(config_file):
            self.logger.info(f"Loading config from {config_file}")
            with open(config_file) as f:
                user_config = yaml.safe_load(f)
                default_config.update(user_config)
                
        return default_config

    def install(self):
        # Append the ISO as CDROM so that installation can run from it.
        self.qemu_args.extend(["-cdrom", self.iso_file])
        self.start()
        while not self.running:
            self.work()

    def bootstrap_spin(self):
        if self.spins > 600:
            self.logger.error("Installation timed out")
            self.stop()
            sys.exit(1)
            
        # Watch for ALL possible installation prompts
        (ridx, match, res) = self.con_expect([
            b"Are you really sure that you want to proceed?",  # Initial warning
            b"32-bit appliance software?",                     # 32-bit question
            b"Keyboard mapping?",                              # Keyboard
            b"Fully Qualified Domain Name?",                   # Hostname
            b"Which interface",                                # Interface
            b"Address?",                                       # IP Address
            b"Netmask length",                                # Netmask
            b"Media",                                         # Media type
            b"Default gateway/router",                        # Gateway
            b"New password:",                                 # Password
            b"Retype new password:",                          # Password confirm
            b"Enable SSH daemon",                             # SSH
            b"Restrict access to Web-GUI",                    # Web restriction
            b"Save configuration to disk",                    # Save config
            b"wait for more?",                               # Final prompt
            b"login:"                                        # Installation complete
        ])
        
        if match:
            self.logger.info(f"Got prompt: {res.decode('utf-8', 'ignore').strip()}")
            if ridx == 0:  # Initial warning
                self.wait_write("yes", None)
            elif ridx == 1:  # 32-bit
                self.wait_write("no", None)
            elif ridx == 2:  # Keyboard
                self.wait_write(self.config['keyboard'], None)
            elif ridx == 3:  # Hostname
                self.wait_write(self.config['hostname'], None)
            elif ridx == 4:  # Interface
                self.wait_write("", None)
            elif ridx == 5:  # Address
                self.wait_write(self.config['address'], None)
            elif ridx == 6:  # Netmask
                self.wait_write(self.config['netmask'], None)
            elif ridx == 7:  # Media
                self.wait_write("", None)
            elif ridx == 8:  # Gateway
                self.wait_write(self.config['gateway'], None)
            elif ridx == 9:  # Password
                self.wait_write(self.config['password'], None)
            elif ridx == 10:  # Password confirm
                self.wait_write(self.config['password'], None)
            elif ridx == 11:  # SSH
                self.wait_write(self.config['enable_ssh'], None)
            elif ridx == 12:  # Web GUI
                self.wait_write(self.config['restrict_web'], None)
            elif ridx == 13:  # Save config
                self.wait_write("yes", None)
            elif ridx == 14:  # Wait for more
                self.wait_write("no", None)
            elif ridx == 15:  # Login prompt (installation complete)
                self.logger.info("Installation completed successfully")
                self.running = True
                self.stop()
            return
        elif res:
            self.write_to_stdout(res)
            
        self.spins += 1

class GENUSCREEN(vrnetlab.VR):
    def __init__(self, hostname, username, password):
        super(GENUSCREEN, self).__init__(username, password)
        self.vms = [ GENUSCREEN_vm(hostname, username, password) ]

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('--trace', action='store_true', help='enable trace level logging')
    parser.add_argument('--username', default='root', help='Username')
    parser.add_argument('--password', default='!Gclab@screen2025', help='Password')
    parser.add_argument("--nics", type=int, default=128, help="Number of NICS")
    parser.add_argument('--hostname', default='genuscreen', help='Router hostname')
    parser.add_argument('--install', action='store_true', help='Run installation')
    parser.add_argument('--connection-mode', default='tc', help='Connection mode')

    args = parser.parse_args()

    LOG_FORMAT = "%(asctime)s: %(module)-10s %(levelname)-8s %(message)s"
    logging.basicConfig(format=LOG_FORMAT)
    logger = logging.getLogger()

    logger.setLevel(logging.DEBUG)
    if args.trace:
        logger.setLevel(TRACE_LEVEL_NUM)

    if args.install:
        installer = GENUSCREEN_INSTALLER()
        installer.install()
    else:
        vr = GENUSCREEN(args.hostname, args.username, args.password)
        vr.start()
