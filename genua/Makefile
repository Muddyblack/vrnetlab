VENDOR=Genua
NAME=Genuscreen

# Set IMAGE_FORMAT based on INSTALL flag
ifeq ($(INSTALL),false)
IMAGE_FORMAT=qcow2
IMAGE_GLOB=*.qcow2
$(info Using qcow2 format for non-install mode)
else
IMAGE_FORMAT=iso
IMAGE_GLOB=*.iso
$(info Using iso format for install mode)
endif

# Match versions like:
# genuscreen-5.0.1.iso or genuscreen-5.0.1.qcow2
VERSION=$(shell echo $(IMAGE) | sed -e 's/genuscreen-\(.*\)\.$(IMAGE_FORMAT)/\1/')

-include ../makefile-sanity.include
-include ../makefile.include

ifeq ($(INSTALL),false)
$(info Install mode disabled)
else
$(info Install mode enabled)
-include ../makefile-install.include
endif