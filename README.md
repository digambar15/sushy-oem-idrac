
Dell EMC OEM extension for sushy
================================

Sushy is a client [library](https://github.com/openstack/sushy) designed to
communicate with [Redfish](https://en.wikipedia.org/wiki/Redfish_(specification))
based BMC.

Redfish specification offers extensibility mechanism to let hardware vendors
introduce their own features with the common Redfish framework. At the same
time, `sushy` supports extending its data model by loading extensions found
within its "oem" namespace.

The `sushy-oem-idrac` package is a sushy extension package that aims at
adding high-level hardware management abstractions, that are specific to
Dell EMC BMC (which is known under the name of iDRAC), to the tree of sushy
Redfish resources.

Example use
-----------

Once installed, sushy user can access Dell EMC OEM resources. For example,
OEM extension of Manager resource can be instrumental for switching the
node to boot from a virtual media device:

```python

import sushy

root = sushy.Sushy('http://mydellemcbmc.example.com')
manager = root.get_manager('iDRAC.Embedded.1')

oem_manager = manager.get_oem_extension('Dell')

oem_manager.set_virtual_boot_device(
    sushy.VIRTUAL_MEDIA_CD, persistent=False, manager=manager)    
```

See full example of virtual media boot setup in the
[functional test suite](https://github.com/etingof/sushy-oem-idrac/blob/master/sushy_oem_idrac/tests/functional/vmedia_boot.py).
