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
import re
import json

import sushy
from sushy.resources import base
from sushy.resources import common
from sushy.resources.oem import base as oem_base

from sushy_oem_idrac import asynchronous
from sushy_oem_idrac import constants
from sushy_oem_idrac import utils

LOG = logging.getLogger(__name__)

class DellManagerActionsField(base.CompositeField):
    import_system_configuration = common.ActionField(
        lambda key, **kwargs: key.endswith(
            '#OemManager.ImportSystemConfiguration'))

class DellManagerIdRefField(base.CompositeField):
    job_service = common.IdRefField(
        lambda key, **kwargs: key.startswith(
            'DellJobService'))

    jobs = common.IdRefField(
        lambda key, **kwargs: key.startswith(
            'Jobs'))

    lc_service = common.IdRefField(
        lambda key, **kwargs: key.startswith(
            'DellLCService'))

class DellManagerExtension(oem_base.OEMResourceBase):

    _actions = DellManagerActionsField('Actions')
    _links = DellManagerIdRefField('Links')

    ACTION_DATA = {
        'ShareParameters': {
            'Target': 'ALL'
        },
        'ImportBuffer': None
    }

    HEADERS = {'content-type': 'application/json'}
    CLEAR_JOBS_URI = '/Actions/DellJobService.DeleteJobQueue'
    REMOTE_API_STATUS_URI = '/Actions/DellLCService.GetRemoteServicesAPIStatus'
    JOB_EXPAND = '?$expand=.($levels=1)'

    # NOTE(etingof): iDRAC job would fail if this XML has
    # insignificant whitespaces

    IDRAC_CONFIG_CD = """\
<SystemConfiguration>\
<Component FQDD="%s">\
<Attribute Name="ServerBoot.1#BootOnce">\
%s\
</Attribute>\
<Attribute Name="ServerBoot.1#FirstBootDevice">\
VCD-DVD\
</Attribute>\
</Component>\
</SystemConfiguration>\
"""

    IDRAC_CONFIG_FLOPPY = """\
<SystemConfiguration>\
<Component FQDD="%s">\
<Attribute Name="ServerBoot.1#BootOnce">\
%s\
</Attribute>\
<Attribute Name="ServerBoot.1#FirstBootDevice">\
VFDD\
</Attribute>\
</Component>\
</SystemConfiguration>\
"""

    IDRAC_MEDIA_TYPES = {
        sushy.VIRTUAL_MEDIA_FLOPPY: IDRAC_CONFIG_FLOPPY,
        sushy.VIRTUAL_MEDIA_CD: IDRAC_CONFIG_CD
    }

    RETRY_COUNT = 10
    RETRY_DELAY = 15

    @property
    def import_system_configuration_uri(self):
        return self._actions.import_system_configuration.target_uri

    @property
    def job_service_uri(self):
        return self._links.job_service.resource_uri

    @property
    def get_jobs_uri(self):
        return self._links.jobs.resource_uri

    @property
    def get_remote_service_api_uri(self):
        return ('%s%s' %
                (self._links.lc_service.resource_uri,
                self.REMOTE_API_STATUS_URI))

    def clear_job_queue(self, job_ids=['JID_CLEARALL']):

        if job_ids is None:
            return None

        delete_job_queue_uri = '%s%s' % (self.job_service_uri, self.CLEAR_JOBS_URI)
        for job_id in job_ids:
            payload = {'JobID':job_id}

            try:
                delete_job_response = asynchronous.http_call(
                        self._conn, 'post',
                        delete_job_queue_uri,
                        headers = self.HEADERS,
                        data = payload,
                        verify = False)
                return delete_job_response

            except (sushy.exceptions.ServerSideError,
                    sushy.exceptions.BadRequestError) as exc:
                LOG.error('Dell OEM clear job queue failed, %s', err_msg)
                raise sushy.exceptions.ServerSideError(error=exc)

    def reset_idrac(self,manager=None):
        payload = {"ResetType":"GracefulRestart"}

        try:
            reset_job_response = asynchronous.http_call(
                            self._conn, 'post',
                            manager._actions.reset.target_uri,
                            data=(payload))

        except (sushy.exceptions.ServerSideError,
                sushy.exceptions.BadRequestError) as exc:
            LOG.error('Dell OEM reset idrac failed, Reason : %s', exc)
            raise sushy.exceptions.ServerSideError(error=exc)

        LOG.info("iDRAC has reset, Waiting for the iDRAC to become ready")
        if(utils.wait_for_idrac_ready(self) == True):
            LOG.info("Dell OEM iDRAC reset successfuly")
            return reset_job_response
        else:
            err_msg = 'Timeout reched to become iDRAC ready'
            LOG.error(err_msg)
            raise sushy.exceptions.ConnectionError(error=err_msg)

    def known_good_state(self,manager=None):
        delete_job_response = self.clear_job_queue(job_ids=['JID_CLEARALL'])
        reset_job_response = self.reset_idrac(manager=manager)
        return [delete_job_response, reset_job_response]

    def get_unfinished_jobs(self):
        jobs_expand_uri = '%s%s' %(self.get_jobs_uri, self.JOB_EXPAND)
        unfinished_jobs = []
        try:
            response = asynchronous.http_call(
                    self._conn, 'get',
                    jobs_expand_uri,
                    verify = False)
            data = response.json()
            for job in data[u'Members']:
                if((job[u'JobState'] == 'Scheduled') or
                      (job[u'JobState'] == 'Running')):
                    unfinished_jobs.append(job['Id'])
            return unfinished_jobs
        except (sushy.exceptions.ServerSideError,
                sushy.exceptions.BadRequestError) as exc:
            LOG.error('Dell OEM clear job queue failed, %s', err_msg)
            raise sushy.exceptions.ServerSideError(error=exc)

    def set_virtual_boot_device(self, device, persistent=False,
                                manager=None, system=None):
        """Set boot device for a node.

        Dell iDRAC Redfish implementation does not support setting
        boot device to virtual media via standard Redfish means.
        However, this still can be done via an OEM extension.

        :param device: Boot device. Values are vendor-specific.
        :param persistent: Whether to set next-boot, or make the change
            permanent. Default: False.
        :raises: InvalidParameterValue if Dell OEM extension can't
            be used.
        :raises: ExtensionError on failure to perform requested
            operation
        """
        try:
            idrac_media = self.IDRAC_MEDIA_TYPES[device]

        except KeyError:
            raise sushy.exceptions.InvalidParameterValue(
                error='Unknown or unsupported device %s' % device)

        idrac_media = idrac_media % (
            manager.identity, 'Disabled' if persistent else 'Enabled')

        action_data = dict(self.ACTION_DATA, ImportBuffer=idrac_media)

        # TODO(etingof): figure out if on-time or persistent boot can at
        # all be implemented via this OEM call

        attempts = self.RETRY_COUNT
        rebooted = False

        while True:
            try:
                response = asynchronous.http_call(
                    self._conn, 'post',
                    self.import_system_configuration_uri,
                    data=action_data,
                    sushy_task_poll_period=1)

                LOG.info("Set boot device to %(device)s via "
                         "Dell OEM magic spell (%(retries)d "
                         "retries)", {'device': device,
                                      'retries': self.RETRY_COUNT - attempts})

                return response

            except (sushy.exceptions.ServerSideError,
                    sushy.exceptions.BadRequestError) as exc:
                LOG.warning(
                    'Dell OEM set boot device failed (attempts left '
                    '%d): %s', attempts, exc)

                errors = exc.body and exc.body.get(
                    '@Message.ExtendedInfo') or []

                for error in errors:
                    message_id = error.get('MessageId')

                    LOG.warning('iDRAC error: %s',
                                error.get('Message', 'Unknown error'))

                    if message_id == constants.IDRAC_CONFIG_PENDING:
                        if not rebooted:
                            LOG.warning(
                                'Let\'s try to turn it off and on again... '
                                'This may consume one-time boot settings if '
                                'set previously!')
                            utils.reboot_system(system)
                            rebooted = True
                            break

                    elif message_id == constants.IDRAC_JOB_RUNNING:
                        pass

                else:
                    time.sleep(self.RETRY_DELAY)

                if not attempts:
                    LOG.error('Too many (%d) retries, bailing '
                              'out.', self.RETRY_COUNT)
                    raise

                attempts -= 1


def get_extension(*args, **kwargs):
    return DellManagerExtension
