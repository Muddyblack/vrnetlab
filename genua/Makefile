VENDOR=Genua
NAME=Genuscreen
IMAGE_FORMAT=qcow2
IMAGE_GLOB=*.qcow2

# Match versions like:
# genuscreen-5.0.1.qcow2
VERSION=$(shell echo $(IMAGE) | sed -e 's/genuscreen-\(.*\)\.qcow2/\1/')

-include ../makefile-sanity.include
-include ../makefile.include

# ifeq ($(INSTALL),false)
# $(info Install mode disabled)
# else
# $(info Install mode enabled)
# -include ../makefile-install.include
# endif
