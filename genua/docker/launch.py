#!/usr/bin/env python3

import datetime
import logging
import os
import re
import signal
import sys

import vrnetlab

def handle_SIGCHLD(signal, frame):
    os.waitpid(-1, os.WNOHANG)

def handle_SIGTERM(signal, frame):
    sys.exit(0)

signal.signal(signal.SIGINT, handle_SIGTERM)
signal.signal(signal.SIGTERM, handle_SIGTERM)
signal.signal(signal.SIGCHLD, handle_SIGCHLD)

TRACE_LEVEL_NUM = 9
logging.addLevelName(TRACE_LEVEL_NUM, "TRACE")

def trace(self, message, *args, **kws):
    if self.isEnabledFor(TRACE_LEVEL_NUM):
        self._log(TRACE_LEVEL_NUM, message, args, **kws)

logging.Logger.trace = trace

class GENUSCREEN_vm(vrnetlab.VM):
    def __init__(self, hostname, username, password):
        
        for e in os.listdir("/"):
            if re.search(".qcow2$", e):
                disk_image = "/" + e

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
            # too many spins with no result -> give up
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

class GENUSCREEN(vrnetlab.VR):
    def __init__(self, hostname, username, password):
        super(GENUSCREEN, self).__init__(username, password)
        self.vms = [ GENUSCREEN_vm(hostname, username, password) ]

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('--trace', action='store_true', help='enable trace level logging')
    parser.add_argument('--username', default='root', help='Username')
    parser.add_argument('--password', default='!DsB@FN€2024', help='Password')
    parser.add_argument('--hostname', default='genuscreen', help='Router hostname')
    parser.add_argument('--connection-mode', default='tc', help='Connection mode')

    args = parser.parse_args()

    LOG_FORMAT = "%(asctime)s: %(module)-10s %(levelname)-8s %(message)s"
    logging.basicConfig(format=LOG_FORMAT)
    logger = logging.getLogger()

    logger.setLevel(logging.DEBUG)
    if args.trace:
        logger.setLevel(TRACE_LEVEL_NUM)

    vr = GENUSCREEN(args.hostname, args.username, args.password)
    vr.start()
