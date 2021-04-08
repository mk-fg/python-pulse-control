# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function

import itertools as it, operator as op, functools as ft
import unittest, contextlib, atexit, signal, threading, select, errno
import os, sys, time, subprocess, tempfile, shutil, socket

if sys.version_info.major > 2: unicode = str

try: import pulsectl
except ImportError:
	sys.path.insert(1, os.path.join(__file__, *['..']*2))
	import pulsectl




class adict(dict):
	def __init__(self, *args, **kws):
		super(adict, self).__init__(*args, **kws)
		self.__dict__ = self


def start_sock_delay_thread(*args):
	# Simple py2/py3 hack to simulate slow network and test conn timeouts
	thread = threading.Thread(target=_sock_delay_thread, args=args)
	thread.daemon = True
	thread.start()
	return thread

def _sock_delay_thread(
		ev_ready, ev_done, ev_disco, bind, connect, delay, block=0.1 ):
	sl = s = c = None
	try:
		sl = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sl.bind(bind)
		sl.listen(1)
		ev_ready.set()
		sl.settimeout(block)
		while True:
			ev_disco.clear()
			while True:
				try: s, addr = sl.accept()
				except socket.timeout: pass
				else: break
				if ev_done.is_set(): return
			ts0 = time.time()
			c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			c.connect(connect)
			s.setblocking(False)
			c.setblocking(False)
			time.sleep(min(delay, max(0, delay - (time.time() - ts0))))
			def _send_data(src, dst, bs=8*2**10):
				while True:
					try:
						buff = src.recv(bs)
						if not buff: break
						dst.sendall(buff) # just assuming it won't get full here
					except socket.error as err:
						if err.errno != errno.EAGAIN: return True
						break
			while True:
				r,w,x = select.select([s,c], [], [s,c], block)
				if x or ev_done.is_set(): return
				if ev_disco.is_set(): break
				if not (r or x): continue
				if c in r and _send_data(c, s): break
				if s in r and _send_data(s, c): break
			s, c = s.close(), c.close()
	finally:
		if c: c.close()
		if s: s.close()
		if sl: sl.close()


def dummy_pulse_init(info=None):
	if not info: info = adict(proc=None, tmp_dir=None)
	try: _dummy_pulse_init(info)
	except Exception:
		dummy_pulse_cleanup(info)
		raise
	return info

def _dummy_pulse_init(info):
	# These are to allow starting pulse with debug logging
	#  or using pre-started (e.g. with gdb attached) instance.
	# Note: PA_REUSE=1234:1234:1235 are localhost tcp ports for tcp modules.
	# For example:
	#  t1% env -i XDG_RUNTIME_DIR=/tmp/pulsectl-tests \
	#       gdb --args /usr/bin/pulseaudio --daemonize=no --fail \
	#       -nF /tmp/pulsectl-tests/conf.pa --exit-idle-time=-1 --log-level=debug
	#  t2% PA_TMPDIR=/tmp/pulsectl-tests PA_REUSE=1234,1235 python -m -m unittest pulsectl.tests.all
	env_tmpdir, env_debug, env_reuse = map(
		os.environ.get, ['PA_TMPDIR', 'PA_DEBUG', 'PA_REUSE'] )
	if not os.environ.get('PATH'): os.environ['PATH'] = '/usr/local/bin:/usr/bin:/bin'

	tmp_base = env_tmpdir or info.get('tmp_dir')
	if not tmp_base:
		tmp_base = info.tmp_dir = tempfile.mkdtemp(prefix='pulsectl-tests.')
		info.sock_unix = None
	tmp_base = os.path.realpath(tmp_base)
	tmp_path = ft.partial(os.path.join, tmp_base)

	# Pick some random available localhost ports
	if not info.get('sock_unix'):
		bind = (
			['127.0.0.1', 0, socket.AF_INET], ['::1', 0, socket.AF_INET6],
			['127.0.0.1', 0, socket.AF_INET], ['127.0.0.1', 0, socket.AF_INET] )
		for n, spec in enumerate(bind):
			if env_reuse:
				spec[1] = int(env_reuse.split(':')[n])
				continue
			addr, p, af = spec
			with contextlib.closing(socket.socket(af, socket.SOCK_STREAM)) as s:
				s.bind((addr, p))
				s.listen(1)
				spec[1] = s.getsockname()[1]
		info.update(
			sock_unix='unix:{}'.format(tmp_path('pulse', 'native')),
			sock_tcp4='tcp4:{}:{}'.format(bind[0][0], bind[0][1]),
			sock_tcp6='tcp6:[{}]:{}'.format(bind[1][0], bind[1][1]),
			sock_tcp_delay='tcp4:{}:{}'.format(bind[2][0], bind[2][1]),
			sock_tcp_delay_src=tuple(bind[2][:2]),
			sock_tcp_delay_dst=tuple(bind[0][:2]),
			sock_tcp_cli=tuple(bind[3][:2]) )

	if not info.get('sock_delay_thread'):
		ev_ready, ev_exit, ev_disco = (threading.Event() for n in range(3))
		delay = info.sock_delay = 0.5
		info.sock_delay_thread_ready = ev_ready
		info.sock_delay_thread_disco = ev_disco
		info.sock_delay_thread_exit = ev_exit
		info.sock_delay_thread = start_sock_delay_thread(
			ev_ready, ev_exit, ev_disco,
			info.sock_tcp_delay_src, info.sock_tcp_delay_dst, delay )

	if info.proc and info.proc.poll() is not None: info.proc = None
	if not env_reuse and not info.get('proc'):
		env = dict( PATH=os.environ['PATH'],
			XDG_RUNTIME_DIR=tmp_base, PULSE_STATE_PATH=tmp_base )
		log_level = 'error' if not env_debug else 'debug'
		info.proc = subprocess.Popen(
			['pulseaudio', '--daemonize=no', '--fail',
				'-nF', '/dev/stdin', '--exit-idle-time=-1', '--log-level={}'.format(log_level)],
			env=env, stdin=subprocess.PIPE )
		bind4, bind6 = info.sock_tcp4.split(':'), info.sock_tcp6.rsplit(':', 1)
		bind4, bind6 = (bind4[1], bind4[2]), (bind6[0].split(':', 1)[1].strip('[]'), bind6[1])
		for line in [
				'module-augment-properties',

				'module-default-device-restore',
				'module-always-sink',
				'module-intended-roles',
				'module-suspend-on-idle',
				'module-position-event-sounds',
				'module-role-cork',
				'module-filter-heuristics',
				'module-filter-apply',
				'module-switch-on-port-available',
				'module-stream-restore',

				'module-native-protocol-tcp auth-anonymous=true'
					' listen={} port={}'.format(*bind4),
				'module-native-protocol-tcp auth-anonymous=true'
					' listen={} port={}'.format(*bind6),
				'module-native-protocol-unix',

				'module-null-sink',
				'module-null-sink' ]:
			if line.startswith('module-'): line = 'load-module {}'.format(line)
			info.proc.stdin.write('{}\n'.format(line).encode('utf-8'))
		info.proc.stdin.close()
		timeout, checks, p = 4, 10, info.sock_unix.split(':', 1)[-1]
		for n in range(checks):
			if not os.path.exists(p):
				time.sleep(float(timeout) / checks)
				continue
			break
		else:
			raise AssertionError( 'pulseaudio process'
				' failed to start or create native socket at {}'.format(p) )

def dummy_pulse_cleanup(info=None, proc=None, tmp_dir=None):
	if not info: info = adict(proc=proc, tmp_dir=tmp_dir)
	if info.proc:
		try: info.proc.terminate()
		except OSError: pass
		timeout, checks = 4, 10
		for n in range(checks):
			if info.proc.poll() is None:
				time.sleep(float(timeout) / checks)
				continue
			break
		else:
			try: info.proc.kill()
			except OSError: pass
		info.proc.wait()
		info.proc = None
	if info.get('sock_delay_thread'):
		info.sock_delay_thread_exit.set()
		info.sock_delay_thread = info.sock_delay_thread.join()
	if info.tmp_dir:
		shutil.rmtree(info.tmp_dir, ignore_errors=True)
		info.tmp_dir = None


class DummyTests(unittest.TestCase):

	instance_info = proc = tmp_dir = None

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
		if cls.instance_info: dummy_pulse_cleanup(cls.instance_info)
		cls.instance_info = cls.proc = cls.tmp_dir = None


	# Fuzzy float comparison is necessary for volume,
	#  as these loose precision when converted to/from pulse int values.

	_compare_floats_rounding = 3
	def _compare_floats(self, a, b, msg=None):
		if round(a, self._compare_floats_rounding) != round(b, self._compare_floats_rounding):
			return self._baseAssertEqual(a, b, msg)

	def __init__(self, *args, **kws):
		super(DummyTests, self).__init__(*args, **kws)
		self.addTypeEqualityFunc(float, self._compare_floats)


	def test_enums(self):
		enum = pulsectl.PulseEventFacilityEnum

		ev_fac_map = dict(sink='sink', sink_input='stream') # hash should match strings
		self.assertTrue(ev_fac_map.get(enum.sink))
		self.assertTrue(ev_fac_map.get(enum.sink_input))

		self.assertEqual(enum.sink, 'sink')
		self.assertEqual(enum['sink'], 'sink')
		self.assertTrue('sink' in enum)

	def test_connect(self):
		with pulsectl.Pulse('t', server=self.sock_unix) as pulse: si = pulse.server_info()
		with pulsectl.Pulse('t', server=self.sock_tcp4) as pulse: si4 = pulse.server_info()
		self.assertEqual(vars(si), vars(si4))
		with pulsectl.Pulse('t', server=self.sock_tcp6) as pulse: si6 = pulse.server_info()
		self.assertEqual(vars(si), vars(si6))

	def test_connect_timeout(self):
		self.sock_delay_thread_ready.wait(timeout=2)
		with pulsectl.Pulse('t', server=self.sock_unix) as pulse: si = pulse.server_info()

		with pulsectl.Pulse('t', server=self.sock_tcp_delay) as pulse: sid = pulse.server_info()
		self.assertEqual(vars(si), vars(sid))
		self.sock_delay_thread_disco.set()

		with pulsectl.Pulse('t', server=self.sock_tcp_delay, connect=False) as pulse:
			pulse.connect()
			sid = pulse.server_info()
		self.assertEqual(vars(si), vars(sid))
		self.sock_delay_thread_disco.set()

		with pulsectl.Pulse('t', server=self.sock_tcp_delay, connect=False) as pulse:
			pulse.connect(1.0)
			sid = pulse.server_info()
		self.assertEqual(vars(si), vars(sid))
		self.sock_delay_thread_disco.set()

		with pulsectl.Pulse('t', server=self.sock_tcp_delay, connect=False) as pulse:
			with self.assertRaises(pulsectl.PulseError): pulse.connect(timeout=0.1)
			self.sock_delay_thread_disco.set()
			pulse.connect(timeout=1.0)
			sid = pulse.server_info()
		self.assertEqual(vars(si), vars(sid))
		self.sock_delay_thread_disco.set()

	def test_server_info(self):
		with pulsectl.Pulse('t', server=self.sock_unix) as pulse:
			si, srcs, sinks = pulse.server_info(), pulse.source_list(), pulse.sink_list()
		self.assertEqual(len(srcs), 2)
		self.assertEqual(len(sinks), 2)

	def test_default_set(self):
		with pulsectl.Pulse('t', server=self.sock_unix) as pulse:
			(src1, src2), (sink1, sink2) = pulse.source_list()[:2], pulse.sink_list()[:2]
			self.assertNotEqual(sink1.name, sink2.name)
			self.assertNotEqual(src1.name, src2.name)

			pulse.default_set(sink1)
			pulse.default_set(sink1)
			pulse.default_set(src1)
			si = pulse.server_info()
			self.assertEqual(si.default_sink_name, sink1.name)
			self.assertEqual(si.default_source_name, src1.name)

			pulse.default_set(sink2)
			si = pulse.server_info()
			self.assertEqual(si.default_sink_name, sink2.name)
			self.assertEqual(si.default_source_name, src1.name)

			pulse.default_set(src2)
			pulse.default_set(src2)
			pulse.default_set(sink1)
			si = pulse.server_info()
			self.assertEqual(si.default_sink_name, sink1.name)
			self.assertEqual(si.default_source_name, src2.name)

			pulse.sink_default_set(sink2.name)
			pulse.source_default_set(src1.name)
			si = pulse.server_info()
			self.assertEqual(si.default_sink_name, sink2.name)
			self.assertEqual(si.default_source_name, src1.name)

			nx = 'xxx'
			self.assertNotIn(nx, [sink1.name, sink2.name])
			self.assertNotIn(nx, [src1.name, src2.name])
			with self.assertRaises(TypeError): pulse.sink_default_set(sink2.index)
			with self.assertRaises(pulsectl.PulseOperationFailed): pulse.sink_default_set(nx)
			with self.assertRaises(pulsectl.PulseOperationFailed): pulse.source_default_set(nx)
			si = pulse.server_info()
			self.assertEqual(si.default_sink_name, sink2.name)
			self.assertEqual(si.default_source_name, src1.name)

	def test_events(self):
		with pulsectl.Pulse('t', server=self.sock_unix) as pulse:
			sink, cb_called = pulse.sink_list()[0], list()
			def ev_cb(ev):
				self.assertEqual(ev.facility, 'sink')
				self.assertEqual(ev.t, 'change')
				self.assertEqual(ev.index, sink.index)
				cb_called.append(True)
				raise pulsectl.PulseLoopStop
			pulse.event_mask_set('all')
			pulse.event_callback_set(ev_cb)
			pulse.volume_set_all_chans(sink, 0.6)
			if not cb_called: pulse.event_listen()
			self.assertTrue(bool(cb_called))
			pulse.event_mask_set('null')
			pulse.event_callback_set(None)

	def test_cli(self):
		xdg_dir_prev = os.environ.get('XDG_RUNTIME_DIR')
		try:
			os.environ['XDG_RUNTIME_DIR'] = self.tmp_dir
			with contextlib.closing(pulsectl.connect_to_cli(as_file=False)) as s:
				s.send(b'dump\n')
				while True:
					try: buff = s.recv(2**20)
					except socket.error: buff = None
					if not buff: raise AssertionError
					if b'### EOF' in buff.splitlines(): break
			with contextlib.closing(pulsectl.connect_to_cli()) as s:
				s.write('dump\n')
				for line in s:
					if line == '### EOF\n': break
				else: raise AssertionError
				s.write(
					'load-module module-cli-protocol-tcp'
					' listen={} port={}\n'.format(*self.sock_tcp_cli) )
			with contextlib.closing(pulsectl.connect_to_cli(self.sock_tcp_cli)) as s:
				s.write('dump\n')
				for line in s:
					if line == '### EOF\n': break
				else: raise AssertionError
				s.write('unload-module module-cli-protocol-tcp\n')
		finally:
			if xdg_dir_prev is not None:
				os.environ['XDG_RUNTIME_DIR'] = xdg_dir_prev

	def test_sink_src(self):
		with pulsectl.Pulse('t', server=self.sock_unix) as pulse:
			src, sink = pulse.source_list()[0], pulse.sink_list()[0]
			self.assertTrue(src.proplist.get('device.class'))
			self.assertTrue(isinstance(src.proplist.get('device.class'), unicode))
			self.assertTrue(isinstance(list(src.proplist.keys())[0], unicode))
			self.assertTrue(sink.proplist.get('device.class'))
			self.assertTrue(isinstance(sink.proplist.get('device.class'), unicode))
			self.assertTrue(isinstance(list(sink.proplist.keys())[0], unicode))

			pulse.mute(src, False)
			self.assertFalse(src.mute)
			self.assertFalse(pulse.source_info(src.index).mute)
			pulse.mute(src, True)
			pulse.mute(src, True)
			self.assertTrue(src.mute)
			self.assertTrue(pulse.source_info(src.index).mute)
			pulse.mute(src, False)

			pulse.mute(sink, False)
			self.assertFalse(sink.mute)
			self.assertFalse(pulse.sink_info(sink.index).mute)
			pulse.mute(sink)
			self.assertTrue(sink.mute)
			self.assertTrue(pulse.sink_info(sink.index).mute)
			pulse.mute(sink, False)

			pulse.volume_set_all_chans(sink, 1.0)
			self.assertEqual(sink.volume.value_flat, 1.0)
			self.assertEqual(pulse.sink_info(sink.index).volume.values, sink.volume.values)
			pulse.volume_set_all_chans(sink, 0.5)
			self.assertEqual(sink.volume.value_flat, 0.5)
			self.assertEqual(pulse.sink_info(sink.index).volume.values, sink.volume.values)
			pulse.volume_change_all_chans(sink, -0.5)
			self.assertEqual(sink.volume.value_flat, 0.0)
			self.assertEqual(pulse.sink_info(sink.index).volume.values, sink.volume.values)
			pulse.volume_set_all_chans(sink, 1.0)

	def test_get_sink_src(self):
		with pulsectl.Pulse('t', server=self.sock_unix) as pulse:
			src, sink = pulse.source_list(), pulse.sink_list()
			src_nx, sink_nx = max(s.index for s in src)+1, max(s.index for s in sink)+1
			src, sink = src[0], sink[0]
			self.assertEqual(sink.index, pulse.get_sink_by_name(sink.name).index)
			self.assertEqual(src.index, pulse.get_source_by_name(src.name).index)
			with self.assertRaises(pulsectl.PulseIndexError): pulse.source_info(src_nx)
			with self.assertRaises(pulsectl.PulseIndexError): pulse.sink_info(sink_nx)

	# def test_get_card(self): no cards to test these calls with :(

	def test_module_funcs(self):
		with pulsectl.Pulse('t', server=self.sock_unix) as pulse:
			self.assertEqual(len(pulse.sink_list()), 2)
			idx = pulse.module_load('module-null-sink')
			self.assertEqual(len(pulse.sink_list()), 3)
			pulse.module_unload(idx)
			self.assertEqual(len(pulse.sink_list()), 2)

	def test_stream(self):
		with pulsectl.Pulse('t', server=self.sock_unix) as pulse:
			stream_started = list()
			def stream_ev_cb(ev):
				if ev.t != 'new': return
				stream_started.append(ev.index)
				raise pulsectl.PulseLoopStop
			pulse.event_mask_set('sink_input')
			pulse.event_callback_set(stream_ev_cb)

			paplay = subprocess.Popen(
				['paplay', '--raw', '/dev/zero'], env=dict(
					PATH=os.environ['PATH'], XDG_RUNTIME_DIR=self.tmp_dir ) )
			try:
				if not stream_started: pulse.event_listen()
				self.assertTrue(bool(stream_started))
				stream_idx, = stream_started

				stream = pulse.sink_input_info(stream_idx)
				self.assertTrue(stream.proplist.get('application.name'))
				self.assertTrue(isinstance(stream.proplist.get('application.name'), unicode))
				self.assertTrue(isinstance(list(stream.proplist.keys())[0], unicode))

				pulse.mute(stream, False)
				self.assertFalse(stream.mute)
				self.assertFalse(pulse.sink_input_info(stream.index).mute)
				pulse.mute(stream)
				self.assertTrue(stream.mute)
				self.assertTrue(pulse.sink_input_info(stream.index).mute)
				pulse.mute(stream, False)

				pulse.volume_set_all_chans(stream, 1.0)
				self.assertEqual(stream.volume.value_flat, 1.0)
				self.assertEqual(pulse.sink_input_info(stream.index).volume.values, stream.volume.values)
				pulse.volume_set_all_chans(stream, 0.5)
				self.assertEqual(stream.volume.value_flat, 0.5)
				self.assertEqual(pulse.sink_input_info(stream.index).volume.values, stream.volume.values)
				pulse.volume_change_all_chans(stream, -0.5)
				self.assertEqual(stream.volume.value_flat, 0.0)
				self.assertEqual(pulse.sink_input_info(stream.index).volume.values, stream.volume.values)

			finally:
				if paplay.poll() is None: paplay.kill()
				paplay.wait()

			with self.assertRaises(pulsectl.PulseIndexError): pulse.sink_input_info(stream.index)

	def test_ext_stream_restore(self):
		sr_name1 = 'sink-input-by-application-name:pulsectl-test-1'
		sr_name2 = 'sink-input-by-application-name:pulsectl-test-2'

		with pulsectl.Pulse('t', server=self.sock_unix) as pulse:
			self.assertIsNotNone(pulse.stream_restore_test())

			pulse.stream_restore_write(sr_name1, volume=0.5, mute=True)
			pulse.stream_restore_write(
				pulsectl.PulseExtStreamRestoreInfo(sr_name2, volume=0.3, channel_list='mono'),
				apply_immediately=True )

			sr_list = pulse.stream_restore_list()
			self.assertIsInstance(sr_list, list)
			self.assertTrue(sr_list)
			sr_dict = dict((sr.name, sr) for sr in sr_list)
			self.assertEqual(sr_dict[sr_name1].volume.value_flat, 0.5)
			self.assertEqual(sr_dict[sr_name1].mute, 1)
			self.assertEqual(sr_dict[sr_name1].channel_list, ['mono'])
			self.assertIn(sr_name2, sr_dict)
			self.assertEqual(sr_dict[sr_name2].channel_list, ['mono'])

			pulse.stream_restore_delete(sr_name1)
			sr_dict = dict((sr.name, sr) for sr in pulse.stream_restore_list())
			self.assertNotIn(sr_name1, sr_dict)
			self.assertIn(sr_name2, sr_dict)

			pulse.stream_restore_write(
				[ pulsectl.PulseExtStreamRestoreInfo( sr_name1,
						volume=0.7, channel_list=['front-left', 'front-right'] ),
					sr_dict[sr_name2] ],
				mode='merge' )
			pulse.stream_restore_write(sr_name1,
				volume=0.3, channel_list='mono', mute=True )
			sr_dict = dict((sr.name, sr) for sr in pulse.stream_restore_list())
			self.assertEqual(sr_dict[sr_name1].volume.value_flat, 0.7)
			self.assertEqual(sr_dict[sr_name1].mute, 0)
			self.assertEqual(sr_dict[sr_name1].channel_list, ['front-left', 'front-right'])

			pulse.stream_restore_write(sr_name1, volume=0.4, mode='replace')
			sr_dict = dict((sr.name, sr) for sr in pulse.stream_restore_list())
			self.assertEqual(sr_dict[sr_name1].volume.value_flat, 0.4)

			pulse.stream_restore_write(sr_name2, volume=0.9, mode='set')
			sr_dict = dict((sr.name, sr) for sr in pulse.stream_restore_list())
			self.assertEqual(sr_dict[sr_name2].volume.value_flat, 0.9)
			self.assertEqual(list(sr_dict.keys()), [sr_name2])

			pulse.stream_restore_write([], mode='set') # i.e. remove all
			sr_dict = dict((sr.name, sr) for sr in pulse.stream_restore_list())
			self.assertNotIn(sr_name1, sr_dict)
			self.assertNotIn(sr_name2, sr_dict)

	def test_stream_move(self):
		with pulsectl.Pulse('t', server=self.sock_unix) as pulse:
			stream_started = list()
			def stream_ev_cb(ev):
				if ev.t != 'new': return
				stream_started.append(ev.index)
				raise pulsectl.PulseLoopStop
			pulse.event_mask_set('sink_input')
			pulse.event_callback_set(stream_ev_cb)

			paplay = subprocess.Popen(
				['paplay', '--raw', '/dev/zero'], env=dict(
					PATH=os.environ['PATH'], XDG_RUNTIME_DIR=self.tmp_dir ) )
			try:
				if not stream_started: pulse.event_listen()
				stream_idx, = stream_started
				stream = pulse.sink_input_info(stream_idx)
				sink_indexes = set(s.index for s in pulse.sink_list())
				sink1 = stream.sink
				sink2 = sink_indexes.difference([sink1]).pop()
				sink_nx = max(sink_indexes) + 1

				pulse.sink_input_move(stream.index, sink2)
				stream_new = pulse.sink_input_info(stream.index)
				self.assertEqual(stream.sink, sink1) # old info doesn't get updated
				self.assertEqual(stream_new.sink, sink2)

				pulse.sink_input_move(stream.index, sink1) # move it back
				stream_new = pulse.sink_input_info(stream.index)
				self.assertEqual(stream_new.sink, sink1)

				with self.assertRaises(pulsectl.PulseOperationFailed):
					pulse.sink_input_move(stream.index, sink_nx)

			finally:
				if paplay.poll() is None: paplay.kill()
				paplay.wait()

	def test_get_peak_sample(self):
		# Note: this test takes at least multiple seconds to run
		with pulsectl.Pulse('t', server=self.sock_unix) as pulse:
			source_any = max(s.index for s in pulse.source_list())
			source_nx = source_any + 1

			time.sleep(0.3) # make sure previous streams die
			peak = pulse.get_peak_sample(source_any, 0.3)
			self.assertEqual(peak, 0)

			stream_started = list()
			def stream_ev_cb(ev):
				if ev.t != 'new': return
				stream_started.append(ev.index)
				raise pulsectl.PulseLoopStop
			pulse.event_mask_set('sink_input')
			pulse.event_callback_set(stream_ev_cb)

			paplay = subprocess.Popen(
				['paplay', '--raw', '/dev/urandom'], env=dict(
					PATH=os.environ['PATH'], XDG_RUNTIME_DIR=self.tmp_dir ) )
			try:
				if not stream_started: pulse.event_listen()
				stream_idx, = stream_started
				si = pulse.sink_input_info(stream_idx)
				sink = pulse.sink_info(si.sink)
				source = pulse.source_info(sink.monitor_source)

				# First poll can randomly fail if too short, probably due to latency or such
				peak = pulse.get_peak_sample(sink.monitor_source, 3)
				self.assertGreater(peak, 0)

				peak = pulse.get_peak_sample(source.index, 0.3, si.index)
				self.assertGreater(peak, 0)
				peak = pulse.get_peak_sample(source.name, 0.3, si.index)
				self.assertGreater(peak, 0)
				peak = pulse.get_peak_sample(source_nx, 0.3)
				self.assertEqual(peak, 0)

				paplay.terminate()
				paplay.wait()

				peak = pulse.get_peak_sample(source.index, 0.3, si.index)
				self.assertEqual(peak, 0)

			finally:
				if paplay.poll() is None: paplay.kill()
				paplay.wait()


class PulseCrashTests(unittest.TestCase):

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

	def test_reconnect(self):
		info = dummy_pulse_init()
		try:
			with pulsectl.Pulse('t', server=info.sock_unix, connect=False) as pulse:
				with self.assertRaises(Exception):
					for si in pulse.sink_list(): raise AssertionError(si)

				pulse.connect(autospawn=False)
				self.assertTrue(pulse.connected)
				for si in pulse.sink_list(): self.assertTrue(si)
				info.proc.terminate()
				info.proc.wait()
				with self.assertRaises(Exception):
					for si in pulse.sink_list(): raise AssertionError(si)
				self.assertFalse(pulse.connected)

				dummy_pulse_init(info)
				pulse.connect(autospawn=False, wait=True)
				self.assertTrue(pulse.connected)
				for si in pulse.sink_list(): self.assertTrue(si)

				pulse.disconnect()
				with self.assertRaises(Exception):
					for si in pulse.sink_list(): raise AssertionError(si)
				self.assertFalse(pulse.connected)
				pulse.connect(autospawn=False)
				self.assertTrue(pulse.connected)
				for si in pulse.sink_list(): self.assertTrue(si)

		finally: dummy_pulse_cleanup(info)


if __name__ == '__main__': unittest.main()
