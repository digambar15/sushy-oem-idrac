# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import logging
import time
import retrying

import sushy
from sushy_oem_idrac import asynchronous

LOG = logging.getLogger(__name__)

_IDRAC_IS_READY_RETRIES = 96
_IDRAC_IS_READY_RETRY_DELAY_SEC =10


def reboot_system(system):
    if system.power_state != sushy.POWER_STATE_OFF:
        system.reset_system(sushy.RESET_FORCE_OFF)
        LOG.info('Requested system power OFF')

    while system.power_state != sushy.POWER_STATE_OFF:
        time.sleep(30)
        system.refresh()

    LOG.info('System is powered OFF')

    system.reset_system(sushy.RESET_ON)

    LOG.info('Requested system power ON')

    while system.power_state != sushy.POWER_STATE_ON:
        time.sleep(30)
        system.refresh()

    LOG.info('System powered ON')

@retrying.retry(
    retry_on_exception=lambda exception: isinstance(exception, Exception),
    stop_max_attempt_number=_IDRAC_IS_READY_RETRIES,
    wait_fixed=_IDRAC_IS_READY_RETRY_DELAY_SEC * 1000)
def wait_for_idrac_ready(oem_manager):
    is_ready_response = is_idrac_ready(oem_manager)
    if "LCStatus" in is_ready_response:
         LOG.info("idrac for node is ready")
         return True
    else:
        err_msg = ('idrac for node is not ready,'
                'Failed to perform drac operation, Retrying it' )
        raise sushy.exception.ConnectionError(error=err_msg)

def is_idrac_ready(oem_manager):

    try:
        response = asynchronous.http_call(
                            oem_manager._conn, 'post',
                            oem_manager.get_remote_service_api_uri,
                            headers=oem_manager.HEADERS,
                            data={},
                            verify=False)
        data = response.json()
    except Exception as err:
        return err
    return data

