# Copyright 2017 Red Hat, Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import json
import mock

from oslotest.base import BaseTestCase
import sushy
from sushy.resources.manager import manager


class ManagerTestCase(BaseTestCase):

    def setUp(self):
        super(ManagerTestCase, self).setUp()
        self.conn = mock.Mock()
        with open('sushy_oem_idrac/tests/unit/json_samples/'
                  'manager.json') as f:
            mock_response = self.conn.get.return_value
            mock_response.json.return_value = json.load(f)
            mock_response.status_code = 200

        mock_response = self.conn.post.return_value
        mock_response.status_code = 202
        mock_response.headers.get.return_value = '1'

        self.manager = manager.Manager(self.conn, '/redfish/v1/Managers/BMC',
                                       redfish_version='1.0.2')

    @mock.patch('sushy.resources.oem.common._global_extn_mgrs_by_resource', {})
    def test_import_system_configuration_uri(self):
        oem = self.manager.get_oem_extension('Dell')

        self.assertEqual(
            '/redfish/v1/Managers/iDRAC.Embedded.1/Actions/Oem/EID_674_Manager'
            '.ImportSystemConfiguration',
            oem.import_system_configuration_uri)

    @mock.patch('sushy.resources.oem.common._global_extn_mgrs_by_resource', {})
    def test_set_virtual_boot_device_cd(self):
        oem = self.manager.get_oem_extension('Dell')

        oem.set_virtual_boot_device(
            sushy.VIRTUAL_MEDIA_CD, manager=self.manager)

        self.conn.post.assert_called_once_with(
            '/redfish/v1/Managers/iDRAC.Embedded.1/Actions/Oem/EID_674_Manager'
            '.ImportSystemConfiguration', data=mock.ANY)
