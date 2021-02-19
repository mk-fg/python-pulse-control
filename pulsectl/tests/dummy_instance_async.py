import asyncio
import atexit
import functools
import os
import signal
import subprocess
import sys
import unittest

import pulsectl
from pulsectl.pulsectl import unicode
from pulsectl.tests.dummy_instance import dummy_pulse_init, dummy_pulse_cleanup


def async_test(f):
    """
    Decorator to transform async unittest coroutines into normal test methods
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(f(*args, **kwargs))
    return wrapper


@unittest.skipUnless(sys.version_info >= (3, 6), "Python 3.6 or higher required for asynchronous interface.")
class AsyncDummyTests(unittest.TestCase):

	proc = tmp_dir = None

	@classmethod
	def setUpClass(cls):
		assert not cls.proc and not cls.tmp_dir, [cls.proc, cls.tmp_dir]

		for sig in 'hup', 'term', 'int':
			signal.signal(getattr(signal, 'sig{}'.format(sig).upper()), lambda sig,frm: sys.exit())
		atexit.register(cls.tearDownClass)

		cls.instance_info = dummy_pulse_init()
		for k, v in cls.instance_info.items(): setattr(cls, k, v)

	@classmethod
	def tearDownClass(cls):
		dummy_pulse_cleanup(cls.instance_info)
		cls.proc = cls.tmp_dir = None


	# Fuzzy float comparison is necessary for volume,
	#  as these loose precision when converted to/from pulse int values.

	_compare_floats_rounding = 3
	def _compare_floats(self, a, b, msg=None):
		if round(a, self._compare_floats_rounding) != round(b, self._compare_floats_rounding):
			return self._baseAssertEqual(a, b, msg)

	def __init__(self, *args, **kws):
		super(AsyncDummyTests, self).__init__(*args, **kws)
		self.addTypeEqualityFunc(float, self._compare_floats)


	@async_test
	async def test_connect(self):
		with pulsectl.PulseAsync('t', server=self.sock_unix) as pulse:
			await pulse.connect()
			si = await pulse.server_info()
		with pulsectl.PulseAsync('t', server=self.sock_tcp4) as pulse:
			await pulse.connect()
			si4 = await pulse.server_info()
		self.assertEqual(vars(si), vars(si4))
		with pulsectl.PulseAsync('t', server=self.sock_tcp6) as pulse:
			await pulse.connect()
			si6 = await pulse.server_info()
		self.assertEqual(vars(si), vars(si6))

	@async_test
	async def test_server_info(self):
		with pulsectl.PulseAsync('t', server=self.sock_unix) as pulse:
			await pulse.connect()
			si, srcs, sinks = await pulse.server_info(), await pulse.source_list(), await pulse.sink_list()
		self.assertEqual(len(srcs), 2)
		self.assertEqual(len(sinks), 2)

	@async_test
	async def test_default_set(self):
		with pulsectl.PulseAsync('t', server=self.sock_unix) as pulse:
			await pulse.connect()
			(src1, src2), (sink1, sink2) = (await pulse.source_list())[:2], (await pulse.sink_list())[:2]
			self.assertNotEqual(sink1.name, sink2.name)
			self.assertNotEqual(src1.name, src2.name)

			await pulse.default_set(sink1)
			await pulse.default_set(sink1)
			await pulse.default_set(src1)
			si = await pulse.server_info()
			self.assertEqual(si.default_sink_name, sink1.name)
			self.assertEqual(si.default_source_name, src1.name)

			await pulse.default_set(sink2)
			si = await pulse.server_info()
			self.assertEqual(si.default_sink_name, sink2.name)
			self.assertEqual(si.default_source_name, src1.name)

			await pulse.default_set(src2)
			await pulse.default_set(src2)
			await pulse.default_set(sink1)
			si = await pulse.server_info()
			self.assertEqual(si.default_sink_name, sink1.name)
			self.assertEqual(si.default_source_name, src2.name)

			await pulse.sink_default_set(sink2.name)
			await pulse.source_default_set(src1.name)
			si = await pulse.server_info()
			self.assertEqual(si.default_sink_name, sink2.name)
			self.assertEqual(si.default_source_name, src1.name)

			nx = 'xxx'
			self.assertNotIn(nx, [sink1.name, sink2.name])
			self.assertNotIn(nx, [src1.name, src2.name])
			with self.assertRaises(TypeError): await pulse.sink_default_set(sink2.index)
			with self.assertRaises(pulsectl.PulseOperationFailed): await pulse.sink_default_set(nx)
			with self.assertRaises(pulsectl.PulseOperationFailed): await pulse.source_default_set(nx)
			si = await pulse.server_info()
			self.assertEqual(si.default_sink_name, sink2.name)
			self.assertEqual(si.default_source_name, src1.name)

	@async_test
	async def test_events(self):
		with pulsectl.PulseAsync ('t', server=self.sock_unix) as pulse:
			await pulse.connect()
			sink, cb_called = (await pulse.sink_list())[0], list()

			async def listen_events():
				async for ev in pulse.subscribe_events('all'):
					self.assertEqual(ev.facility, 'sink')
					self.assertEqual(ev.t, 'change')
					self.assertEqual(ev.index, sink.index)
					cb_called.append(True)
					break
			task = asyncio.create_task(listen_events())
			await asyncio.sleep(0)

			await pulse.volume_set_all_chans(sink, 0.6)
			await asyncio.sleep(0.05)
			self.assertTrue(bool(cb_called))
			self.assertIsNone(pulse.event_callback)

	@async_test
	async def test_sink_src(self):
		with pulsectl.PulseAsync('t', server=self.sock_unix) as pulse:
			await pulse.connect()
			src, sink = (await pulse.source_list())[0], (await pulse.sink_list())[0]
			self.assertTrue(src.proplist.get('device.class'))
			self.assertTrue(isinstance(src.proplist.get('device.class'), unicode))
			self.assertTrue(isinstance(list(src.proplist.keys())[0], unicode))
			self.assertTrue(sink.proplist.get('device.class'))
			self.assertTrue(isinstance(sink.proplist.get('device.class'), unicode))
			self.assertTrue(isinstance(list(sink.proplist.keys())[0], unicode))

			await pulse.mute(src, False)
			print(repr(src))
			self.assertFalse(src.mute)
			self.assertFalse((await pulse.source_info(src.index)).mute)
			await pulse.mute(src, True)
			await pulse.mute(src, True)
			self.assertTrue(src.mute)
			self.assertTrue((await pulse.source_info(src.index)).mute)
			await pulse.mute(src, False)

			await pulse.mute(sink, False)
			self.assertFalse(sink.mute)
			self.assertFalse((await pulse.sink_info(sink.index)).mute)
			await pulse.mute(sink)
			self.assertTrue(sink.mute)
			self.assertTrue((await pulse.sink_info(sink.index)).mute)
			await pulse.mute(sink, False)

			await pulse.volume_set_all_chans(sink, 1.0)
			self.assertEqual(sink.volume.value_flat, 1.0)
			self.assertEqual((await pulse.sink_info(sink.index)).volume.values, sink.volume.values)
			await pulse.volume_set_all_chans(sink, 0.5)
			self.assertEqual(sink.volume.value_flat, 0.5)
			self.assertEqual((await pulse.sink_info(sink.index)).volume.values, sink.volume.values)
			await pulse.volume_change_all_chans(sink, -0.5)
			self.assertEqual(sink.volume.value_flat, 0.0)
			self.assertEqual((await pulse.sink_info(sink.index)).volume.values, sink.volume.values)
			await pulse.volume_set_all_chans(sink, 1.0)

	@async_test
	async def test_get_sink_src(self):
		with pulsectl.PulseAsync('t', server=self.sock_unix) as pulse:
			await pulse.connect()
			src, sink = await pulse.source_list(), await pulse.sink_list()
			src_nx, sink_nx = max(s.index for s in src)+1, max(s.index for s in sink)+1
			src, sink = src[0], sink[0]
			self.assertEqual(sink.index, (await pulse.get_sink_by_name(sink.name)).index)
			self.assertEqual(src.index, (await pulse.get_source_by_name(src.name)).index)
			with self.assertRaises(pulsectl.PulseIndexError): await pulse.source_info(src_nx)
			with self.assertRaises(pulsectl.PulseIndexError): await pulse.sink_info(sink_nx)

	# def test_get_card(self): no cards to test these calls with :(

	@async_test
	async def test_module_funcs(self):
		with pulsectl.PulseAsync('t', server=self.sock_unix) as pulse:
			await pulse.connect()
			self.assertEqual(len(await pulse.sink_list()), 2)
			idx = await pulse.module_load('module-null-sink')
			self.assertEqual(len(await pulse.sink_list()), 3)
			await pulse.module_unload(idx)
			self.assertEqual(len(await pulse.sink_list()), 2)

	@async_test
	async def test_stream(self):
		with pulsectl.PulseAsync('t', server=self.sock_unix) as pulse:
			await pulse.connect()
			stream_started = asyncio.Event()
			stream_idx = []

			async def listen_stream_events():
				async for ev in pulse.subscribe_events('sink_input'):
					if ev.t == 'new':
						stream_idx.append(ev.index)
						stream_started.set()
						break

			asyncio.create_task(listen_stream_events())

			paplay = subprocess.Popen(
				['paplay', '--raw', '/dev/zero'], env=dict(
					PATH=os.environ['PATH'], XDG_RUNTIME_DIR=self.tmp_dir ) )
			try:
				await stream_started.wait()
				self.assertTrue(bool(stream_idx))
				stream_idx = stream_idx[0]

				stream = await pulse.sink_input_info(stream_idx)
				self.assertTrue(stream.proplist.get('application.name'))
				self.assertTrue(isinstance(stream.proplist.get('application.name'), unicode))
				self.assertTrue(isinstance(list(stream.proplist.keys())[0], unicode))

				await pulse.mute(stream, False)
				self.assertFalse(stream.mute)
				self.assertFalse((await pulse.sink_input_info(stream.index)).mute)
				await pulse.mute(stream)
				self.assertTrue(stream.mute)
				self.assertTrue((await pulse.sink_input_info(stream.index)).mute)
				await pulse.mute(stream, False)

				await pulse.volume_set_all_chans(stream, 1.0)
				self.assertEqual(stream.volume.value_flat, 1.0)
				self.assertEqual((await pulse.sink_input_info(stream.index)).volume.values, stream.volume.values)
				await pulse.volume_set_all_chans(stream, 0.5)
				self.assertEqual(stream.volume.value_flat, 0.5)
				self.assertEqual((await pulse.sink_input_info(stream.index)).volume.values, stream.volume.values)
				await pulse.volume_change_all_chans(stream, -0.5)
				self.assertEqual(stream.volume.value_flat, 0.0)
				self.assertEqual((await pulse.sink_input_info(stream.index)).volume.values, stream.volume.values)

			finally:
				if paplay.poll() is None: paplay.kill()
				paplay.wait()

			with self.assertRaises(pulsectl.PulseIndexError):
				await pulse.sink_input_info(stream.index)

	@async_test
	async def test_ext_stream_restore(self):
		sr_name1 = 'sink-input-by-application-name:pulsectl-test-1'
		sr_name2 = 'sink-input-by-application-name:pulsectl-test-2'

		with pulsectl.PulseAsync('t', server=self.sock_unix) as pulse:
			await pulse.connect()
			self.assertIsNotNone(await pulse.stream_restore_test())

			await pulse.stream_restore_write(sr_name1, volume=0.5, mute=True)
			await pulse.stream_restore_write(
				pulsectl.PulseExtStreamRestoreInfo(sr_name2, volume=0.3, channel_list='mono'),
				apply_immediately=True )

			sr_list = await pulse.stream_restore_list()
			self.assertIsInstance(sr_list, list)
			self.assertTrue(sr_list)
			sr_dict = dict((sr.name, sr) for sr in sr_list)
			self.assertEqual(sr_dict[sr_name1].volume.value_flat, 0.5)
			self.assertEqual(sr_dict[sr_name1].mute, 1)
			self.assertEqual(sr_dict[sr_name1].channel_list, ['mono'])
			self.assertIn(sr_name2, sr_dict)
			self.assertEqual(sr_dict[sr_name2].channel_list, ['mono'])

			await pulse.stream_restore_delete(sr_name1)
			sr_dict = dict((sr.name, sr) for sr in await pulse.stream_restore_list())
			self.assertNotIn(sr_name1, sr_dict)
			self.assertIn(sr_name2, sr_dict)

			await pulse.stream_restore_write(
				[ pulsectl.PulseExtStreamRestoreInfo( sr_name1,
						volume=0.7, channel_list=['front-left', 'front-right'] ),
					sr_dict[sr_name2] ],
				mode='merge' )
			await pulse.stream_restore_write(sr_name1,
				volume=0.3, channel_list='mono', mute=True )
			sr_dict = dict((sr.name, sr) for sr in await pulse.stream_restore_list())
			self.assertEqual(sr_dict[sr_name1].volume.value_flat, 0.7)
			self.assertEqual(sr_dict[sr_name1].mute, 0)
			self.assertEqual(sr_dict[sr_name1].channel_list, ['front-left', 'front-right'])

			await pulse.stream_restore_write(sr_name1, volume=0.4, mode='replace')
			sr_dict = dict((sr.name, sr) for sr in await pulse.stream_restore_list())
			self.assertEqual(sr_dict[sr_name1].volume.value_flat, 0.4)

			await pulse.stream_restore_write(sr_name2, volume=0.9, mode='set')
			sr_dict = dict((sr.name, sr) for sr in await pulse.stream_restore_list())
			self.assertEqual(sr_dict[sr_name2].volume.value_flat, 0.9)
			self.assertEqual(list(sr_dict.keys()), [sr_name2])

			await pulse.stream_restore_write([], mode='set') # i.e. remove all
			sr_dict = dict((sr.name, sr) for sr in await pulse.stream_restore_list())
			self.assertNotIn(sr_name1, sr_dict)
			self.assertNotIn(sr_name2, sr_dict)

	@async_test
	async def test_stream_move(self):
		with pulsectl.PulseAsync('t', server=self.sock_unix) as pulse:
			await pulse.connect()
			stream_started = asyncio.Event()
			stream_idx = []

			async def listen_stream_events():
				async for ev in pulse.subscribe_events('sink_input'):
					if ev.t == 'new':
						stream_idx.append(ev.index)
						stream_started.set()
						break

			asyncio.create_task(listen_stream_events())

			paplay = subprocess.Popen(
				['paplay', '--raw', '/dev/zero'], env=dict(
					PATH=os.environ['PATH'], XDG_RUNTIME_DIR=self.tmp_dir ) )
			try:
				await stream_started.wait()
				self.assertTrue(bool(stream_idx))
				stream_idx = stream_idx[0]

				stream = await pulse.sink_input_info(stream_idx)
				sink_indexes = set(s.index for s in await pulse.sink_list())
				sink1 = stream.sink
				sink2 = sink_indexes.difference([sink1]).pop()
				sink_nx = max(sink_indexes) + 1

				await pulse.sink_input_move(stream.index, sink2)
				stream_new = await pulse.sink_input_info(stream.index)
				self.assertEqual(stream.sink, sink1) # old info doesn't get updated
				self.assertEqual(stream_new.sink, sink2)

				await pulse.sink_input_move(stream.index, sink1) # move it back
				stream_new = await pulse.sink_input_info(stream.index)
				self.assertEqual(stream_new.sink, sink1)

				with self.assertRaises(pulsectl.PulseOperationFailed):
					await pulse.sink_input_move(stream.index, sink_nx)

			finally:
				if paplay.poll() is None: paplay.kill()
				paplay.wait()

	@async_test
	async def test_get_peak_sample(self):
		# Note: this test takes at least multiple seconds to run
		with pulsectl.PulseAsync('t', server=self.sock_unix) as pulse:
			await pulse.connect()
			source_any = max(s.index for s in await pulse.source_list())
			source_nx = source_any + 1

			await asyncio.sleep(0.3) # make sure previous streams die
			peak = await pulse.get_peak_sample(source_any, 0.3)
			self.assertEqual(peak, 0)

			stream_started = asyncio.Event()
			stream_idx = []

			async def listen_stream_events():
				async for ev in pulse.subscribe_events('sink_input'):
					if ev.t == 'new':
						stream_idx.append(ev.index)
						stream_started.set()
						break

			asyncio.create_task(listen_stream_events())

			paplay = subprocess.Popen(
				['paplay', '--raw', '/dev/zero'], env=dict(
					PATH=os.environ['PATH'], XDG_RUNTIME_DIR=self.tmp_dir))
			try:
				await stream_started.wait()
				self.assertTrue(bool(stream_idx))
				stream_idx = stream_idx[0]
				si = await pulse.sink_input_info(stream_idx)
				sink = await pulse.sink_info(si.sink)
				source = await pulse.source_info(sink.monitor_source)

				# First poll can randomly fail if too short, probably due to latency or such
				peak = await pulse.get_peak_sample(sink.monitor_source, 3)
				self.assertGreater(peak, 0)

				peak = await pulse.get_peak_sample(source.index, 0.3, si.index)
				self.assertGreater(peak, 0)
				peak = await pulse.get_peak_sample(source.name, 0.3, si.index)
				self.assertGreater(peak, 0)
				peak = await pulse.get_peak_sample(source_nx, 0.3)
				self.assertEqual(peak, 0)

				paplay.terminate()
				paplay.wait()

				peak = await pulse.get_peak_sample(source.index, 0.3, si.index)
				self.assertEqual(peak, 0)

			finally:
				if paplay.poll() is None: paplay.kill()
				paplay.wait()


@unittest.skipUnless(sys.version_info >= (3, 6), "Python 3.6 or higher required for asynchronous interface.")
class PulseCrashTestsAsync(unittest.TestCase):

	@classmethod
	def setUpClass(cls):
		for sig in 'hup', 'term', 'int':
			signal.signal(getattr(signal, 'sig{}'.format(sig).upper()), lambda sig,frm: sys.exit())

	def test_crash_after_connect(self):
		info = dummy_pulse_init()
		try:
			with pulsectl.Pulse('t', server=info.sock_unix) as pulse:
				for si in pulse.sink_list(): self.assertTrue(si)
				info.proc.terminate()
				info.proc.wait()
				with self.assertRaises(pulsectl.PulseOperationFailed):
					for si in pulse.sink_list(): raise AssertionError(si)
				self.assertFalse(pulse.connected)
		finally: dummy_pulse_cleanup(info)

	@async_test
	async def test_reconnect(self):
		info = dummy_pulse_init()
		try:
			with pulsectl.PulseAsync('t', server=info.sock_unix) as pulse:
				with self.assertRaises(Exception):
					for si in await pulse.sink_list(): raise AssertionError(si)

				await pulse.connect(autospawn=False)
				self.assertTrue(pulse.connected.is_set())
				for si in await pulse.sink_list(): self.assertTrue(si)
				info.proc.terminate()
				info.proc.wait()
				with self.assertRaises(Exception):
					for si in await pulse.sink_list(): raise AssertionError(si)
				self.assertFalse(pulse.connected.is_set())

				dummy_pulse_init(info)
				await pulse.connect(autospawn=False, wait=True)
				self.assertTrue(pulse.connected.is_set())
				for si in await pulse.sink_list(): self.assertTrue(si)

				pulse.disconnect()
				with self.assertRaises(Exception):
					for si in await pulse.sink_list(): raise AssertionError(si)
				self.assertFalse(pulse.connected.is_set())
				await pulse.connect(autospawn=False)
				self.assertTrue(pulse.connected.is_set())
				for si in await pulse.sink_list(): self.assertTrue(si)

		finally: dummy_pulse_cleanup(info)
