import os
import stat
import unittest
import unittest.mock as mock
import uuid

import tapdisk_pause
import VDI
import vhdutil

SYSTEMCTL = '/usr/bin/systemctl'
MOCK_CBT_LOG = 'mock_cbt_log_path'


class TestTapdiskPause(unittest.TestCase):

    def setUp(self):
        self.mock_session = mock.MagicMock(name="MockSession")
        lock_patcher = mock.patch('tapdisk_pause.Lock', autospec=True)
        self.mock_lock = lock_patcher.start()

        exists_patcher = mock.patch('tapdisk_pause.os.path.exists',
                                    autospec=True)
        self.mock_exists = exists_patcher.start()

        readlink_patcher = mock.patch('tapdisk_pause.os.readlink',
                                      autospec=True)
        self.mock_readlink = readlink_patcher.start()

        stat_patcher = mock.patch('tapdisk_pause.os.stat', autospec=True)
        self.mock_stat = stat_patcher.start()

        blktap_patcher = mock.patch('tapdisk_pause.blktap2', autospec=True)
        self.mock_blktap = blktap_patcher.start()
        # Always return the common blktap major
        self.mock_blktap.Tapdisk.major.return_value = 254

        vdi_patcher = mock.patch('VDI.VDI.from_uuid', name='MockVDI')
        self.mock_vdi = vdi_patcher.start()

        util_patcher = mock.patch('rate_control.util', autospec=True)
        self.mock_util = util_patcher.start()

        vhdutil_patcher = mock.patch('tapdisk_pause.vhdutil')
        self.mock_vhdutil = vhdutil_patcher.start()
        self.mock_vhdutil.VDI_TYPE_VHD = vhdutil.VDI_TYPE_VHD

        lvmcache_patcher = mock.patch('tapdisk_pause.lvmcache', autospec=True)
        self.mock_lvmcache = lvmcache_patcher.start()

        self.addCleanup(mock.patch.stopall)

    def test_pause_success(self):
        """
        Test pausing a tapdisk
        """
        sr_uuid = str(uuid.uuid4())
        vdi_uuid = str(uuid.uuid4())

        self.mock_exists.return_value = True

        result = tapdisk_pause.tapPause(
            self.mock_session,
            args={'sr_uuid': sr_uuid, 'vdi_uuid': vdi_uuid})

        self.assertEqual('True', result)

    def test_pause_nopath(self):
        """
        Test pausing a tapdisk when not found succeeds
        """
        sr_uuid = str(uuid.uuid4())
        vdi_uuid = str(uuid.uuid4())

        self.mock_exists.return_value = False

        result = tapdisk_pause.tapPause(
            self.mock_session,
            args={'sr_uuid': sr_uuid, 'vdi_uuid': vdi_uuid})

        self.assertEqual('True', result)

    def test_unpause_nopath_sucess(self):
        """
        Test unpause for missing path is a success
        """
        sr_uuid = str(uuid.uuid4())
        vdi_uuid = str(uuid.uuid4())

        self.mock_exists.return_value = False

        result = tapdisk_pause.tapUnpause(
            self.mock_session,
            args={'sr_uuid': sr_uuid, 'vdi_uuid': vdi_uuid})

        self.assertEqual('True', result)

    def test_unpause_no_rate_limit(self):
        """
        Test unpausing a tapdisk without a rate limit
        """
        sr_uuid = str(uuid.uuid4())
        vdi_uuid = str(uuid.uuid4())

        self.mock_exists.return_value = True

        self.mock_vdi()._get_blocktracking_status.return_value = False
        self.mock_vdi().has_rate_limit.return_value = False
        self.mock_vdi().uuid = vdi_uuid

        result = tapdisk_pause.tapUnpause(
            self.mock_session,
            args={'sr_uuid': sr_uuid, 'vdi_uuid': vdi_uuid})

        self.assertEqual('True', result)
        self.check_unpause_called(cbt_log=None, rate_socket=None)
        self.assertEqual(1, self.mock_util.doexec.call_count)
        # As systemd replaces - with / check we call with escaped uuid
        self.mock_util.doexec.assert_called_with([
            SYSTEMCTL, 'stop',
            'td-rated@%s' % (vdi_uuid.replace('-', '\\x2d'))])

    def test_unpause_with_rate_limit(self):
        """
        Test unpausing a tapdisk without a rate limit
        """
        sr_uuid = str(uuid.uuid4())
        vdi_uuid = str(uuid.uuid4())

        self.mock_exists.return_value = True

        self.mock_vdi()._get_blocktracking_status.return_value = False
        self.mock_vdi().has_rate_limit.return_value = True
        self.mock_vdi().uuid = vdi_uuid

        result = tapdisk_pause.tapUnpause(
            self.mock_session,
            args={'sr_uuid': sr_uuid, 'vdi_uuid': vdi_uuid})

        self.assertEqual('True', result)
        self.check_unpause_called(
            cbt_log=None,
            rate_socket=self.make_rate_socket_name(vdi_uuid))
        self.check_start_called(vdi_uuid)

    def test_unpause_with_cbt(self):
        """
        Test unpause with CBT log attaches the log
        """
        sr_uuid = str(uuid.uuid4())
        vdi_uuid = str(uuid.uuid4())

        self.mock_exists.return_value = True

        self.mock_vdi()._get_blocktracking_status.return_value = True
        self.mock_vdi()._get_cbt_logpath.return_value = (
            MOCK_CBT_LOG)
        self.mock_vdi().has_rate_limit.return_value = True
        self.mock_vdi().uuid = vdi_uuid

        result = tapdisk_pause.tapUnpause(
            self.mock_session,
            args={'sr_uuid': sr_uuid, 'vdi_uuid': vdi_uuid})

        self.assertEqual('True', result)
        self.check_unpause_called(
            cbt_log=MOCK_CBT_LOG,
            rate_socket=self.make_rate_socket_name(vdi_uuid))
        self.check_start_called(vdi_uuid)

    def test_unpause_activate_no_parents(self):
        """
        Test unpause with LVM activate with no parents
        """
        sr_uuid = str(uuid.uuid4())
        vdi_uuid = str(uuid.uuid4())

        self.mock_exists.return_value = True

        self.mock_vdi()._get_blocktracking_status.return_value = True
        self.mock_vdi()._get_cbt_logpath.return_value = (
            MOCK_CBT_LOG)
        self.mock_vdi().has_rate_limit.return_value = True
        self.mock_vdi().uuid = vdi_uuid

        result = tapdisk_pause.tapUnpause(
            self.mock_session,
            args={'sr_uuid': sr_uuid, 'vdi_uuid': vdi_uuid,
                  'activate_parents': 'true'})

        self.assertEqual('True', result)
        self.check_unpause_called(
            cbt_log=MOCK_CBT_LOG,
            rate_socket=self.make_rate_socket_name(vdi_uuid))
        self.check_start_called(vdi_uuid)
        self.assertEqual(
            0, self.mock_lvmcache.LVMCache.return_value.activate.call_count)

    def test_unpause_activate_parents(self):
        """
        Test unpause with LVM activate parents
        """
        sr_uuid = str(uuid.uuid4())
        vdi_uuid = str(uuid.uuid4())

        self.mock_exists.return_value = True

        self.mock_vdi()._get_blocktracking_status.return_value = False
        self.mock_vdi().has_rate_limit.return_value = True
        self.mock_vdi().uuid = vdi_uuid
        self.mock_vhdutil.getParentChain.return_value = {
            vdi_uuid: '/dev/VG_XenStorage-%s/VHD-%s' % (sr_uuid, vdi_uuid),
            'par1_uuid': '/dev/VG_XenStorage-%s/par1_lv' % (sr_uuid),
            'par2_uuid': '/dev/VG_XenStorage-%s/par2_lv' % (sr_uuid)
            }

        result = tapdisk_pause.tapUnpause(
            self.mock_session,
            args={'sr_uuid': sr_uuid, 'vdi_uuid': vdi_uuid,
                  'activate_parents': 'true'})

        self.assertEqual('True', result)
        self.check_unpause_called(
            cbt_log=None,
            rate_socket=self.make_rate_socket_name(vdi_uuid))
        self.check_start_called(vdi_uuid)
        self.assertEqual(
            2, self.mock_lvmcache.LVMCache.return_value.activate.call_count)

    def check_start_called(self, vdi_uuid):
        """
        Check that start is called on the td-rated-service
        """
        self.assertEqual(1, self.mock_util.pread.call_count)
        # As systemd replaces - with / check we call with escaped uuid
        self.mock_util.pread.assert_called_with([
            SYSTEMCTL, 'start',
            'td-rated@%s' % (vdi_uuid.replace('-', '\\x2d'))],
            quiet=True)

    def check_unpause_called(self, cbt_log, rate_socket):
        """
        Check that unpause is called with expected parametes
        """
        self.mock_blktap.Tapdisk.get().unpause.assert_called_with(
            mock.ANY, mock.ANY, None, cbt_log, rate_socket)

    def make_rate_socket_name(self, vdi_uuid):
        return '/run/sm/rated-%s.sk' % vdi_uuid


class TestVdiRateControl(unittest.TestCase):

    def setUp(self) -> None:
        self.mock_sr = mock.MagicMock(name='MockSR')
        self.mock_xapi = mock.MagicMock(name='MockXapi')
        self.mock_sr.session.xenapi = self.mock_xapi
        self.vdi_uuid = str(uuid.uuid4())
        self.test_vdi = VDI.VDI(self.mock_sr, self.vdi_uuid)

    def test_has_rate_limit_no(self):
        # Arrange
        sm_config = {}
        test_xapi_vdi = mock.create_autospec(VDI)

        self.mock_xapi.VDI.get_by_uuid.return_value = test_xapi_vdi
        self.mock_xapi.VDI.get_sm_config.return_value = sm_config

        # Act/Assert
        self.assertFalse(self.test_vdi.has_rate_limit())

    def test_has_rate_limit_yes(self):
        # Arrange
        sm_config = {
            VDI.DB_RATE_LIMIT: 697194.0797842839
        }
        test_xapi_vdi = mock.create_autospec(VDI)

        self.mock_xapi.VDI.get_by_uuid.return_value = test_xapi_vdi
        self.mock_xapi.VDI.get_sm_config.return_value = sm_config

        # Act/Assert
        self.assertTrue(self.test_vdi.has_rate_limit())
