# -*- coding: utf-8 -*-
from __future__ import print_function

import itertools as it, operator as op, functools as ft
from collections import defaultdict
from contextlib import contextmanager
import sys, inspect, traceback

from . import _pulsectl as c


if sys.version_info.major >= 3:
	decodable = bytes
	print_err = ft.partial(print, file=sys.stderr, flush=True)
else:
	range, map, decodable = xrange, it.imap, type('nx', (object,), dict())
	def print_err(*args, **kws):
		kws.setdefault('file', sys.stderr)
		print(*args, **kws)
		kws['file'].flush()
def str_decode(s): return s if not isinstance(s, decodable) else s.decode()


class PulseError(Exception): pass
class PulseOperationFailed(PulseError): pass
class PulseOperationInvalid(PulseOperationFailed): pass
class PulseIndexError(PulseError): pass

class PulseLoopStop(Exception): pass
class PulseDisconnected(Exception): pass

class PulseObject(object):

	def __init__(self, struct=None, *field_data_list, **field_data_dict):
		field_data, fields = dict(), getattr(self, 'c_struct_fields', list())
		if isinstance(fields, str): fields = self.c_struct_fields = fields.split()
		if field_data_list: field_data.update(zip(fields, field_data_list))
		if field_data_dict: field_data.update(field_data_dict)
		if struct is None: field_data, struct = dict(), field_data
		assert not set(field_data.keys()).difference(fields)
		if field_data: self._copy_struct_fields(field_data, fields=field_data.keys())
		self._copy_struct_fields(struct, fields=set(fields).difference(field_data.keys()))

		if struct:
			if hasattr(struct, 'proplist'):
				self.proplist, state = dict(), c.c_void_p()
				while True:
					k = c.pa.proplist_iterate(struct.proplist, c.byref(state))
					if not k: break
					self.proplist[k] = c.pa.proplist_gets(struct.proplist, k)
			if hasattr(struct, 'volume'):
				self.volume = PulseVolumeInfo(struct.volume)
			if hasattr(struct, 'n_ports'):
				self.port_list = list(
					PulsePortInfo(struct.ports[n].contents)
					for n in range(struct.n_ports) )
			if hasattr(struct, 'active_port'):
				self.port_active = None if not struct.active_port\
					else PulsePortInfo(struct.active_port.contents)
			if hasattr(struct, 'channel_map'):
				s = c.create_string_buffer(b'\0' * 512)
				c.pa.channel_map_snprint(s, len(s), struct.channel_map)
				s = str_decode(s.value.strip().split(b','))
				self.channel_count = struct.channel_map.channels
				self.channel_list = s if len(s) == self.channel_count else None

	def _copy_struct_fields(self, struct, fields=None):
		if not fields: fields = self.c_struct_fields
		for k in fields:
			setattr(self, k, str_decode(
				getattr(struct, k) if not isinstance(struct, dict) else struct[k] ))

	def _as_str(self, ext=None, fields=None, **kws):
		kws = list(it.starmap('{}={!r}'.format, kws.items()))
		if fields:
			if isinstance(fields, str): fields = fields.split()
			kws.extend('{}={!r}'.format(k, getattr(self, k)) for k in fields)
		kws = sorted(kws)
		if ext: kws.append(str(ext))
		return ', '.join(kws)

	def __str__(self):
		return self._as_str(fields=self.c_struct_fields)

	def __repr__(self):
		return '<{} at {:x} - {}>'.format(self.__class__.__name__, id(self), str(self))


class PulsePortInfo(PulseObject):
	c_struct_fields = 'name description priority'

	def __eq__(self, o):
		if not isinstance(o, PulsePortInfo): raise TypeError(o)
		return self.name == o.name

	def __hash__(self): return hash(self.name)

class PulseCardInfo(PulseObject):
	c_struct_fields = 'name index driver owner_module n_profiles'

class PulseClientInfo(PulseObject):
	c_struct_fields = 'name index driver owner_module'

class PulseSinkInfo(PulseObject):
	c_struct_fields = ( 'index name mute'
		' description sample_spec owner_module latency driver'
		' monitor_source monitor_source_name flags configured_latency' )

	def __str__(self):
		return self._as_str(self.volume, fields='index name description mute')

class PulseSinkInputInfo(PulseObject):
	c_struct_fields = ( 'index name mute client'
		' owner_module sink sample_spec'
		' buffer_usec sink_usec resample_method driver' )

	def __str__(self):
		return self._as_str(fields='index name mute')

class PulseSourceInfo(PulseObject):
	c_struct_fields = ( 'index name mute'
		' description sample_spec owner_module latency driver monitor_of_sink'
		' monitor_of_sink_name flags configured_latency' )

	def __str__(self):
		return self._as_str(self.volume, fields='index name description mute')

class PulseSourceOutputInfo(PulseObject):
	c_struct_fields = ( 'index name mute client'
		' owner_module source sample_spec'
		' buffer_usec source_usec resample_method driver' )

	def __str__(self):
		return self._as_str(fields='index name mute')

class PulseVolumeInfo(PulseObject):

	def __init__(self, struct):
		self.values = list( (x / c.PA_VOLUME_NORM)
			for x in map(float, struct.values[:struct.channels]) )

	@property
	def value_flat(self): return sum(self.values) / float(len(self.values))
	@value_flat.setter
	def value_flat(self, v): self.values = [v] * len(self.values)

	def to_struct(self):
		struct = c.PA_CVOLUME()
		struct.channels = len(self.values)
		for x in range(struct.channels):
			struct.values[x] = min( c.PA_VOLUME_UI_MAX,
				int(round(self.values[x] * c.PA_VOLUME_NORM)) )
		return struct

	def __str__(self):
		return self._as_str( channels=len(self.values),
			volumes=' / '.join('{}%'.format(int(round(v*100))) for v in self.values) )

class PulseEventInfo(PulseObject):

	def __init__(self, ev_t, facility, index):
		self.t, self.facility, self.index = ev_t, facility, index

	def __str__(self):
		return self._as_str(fields='t facility index'.split())


class Pulse(object):

	def __init__(self, client_name=None, server=None, connect=True, threading_lock=False):
		'''Connects to specified pulse server by default.
			Specifying "connect=False" here prevents that, but be sure to call connect() later.
			"connect=False" can also be used here to
				have control over options passed to connect() method.
			"threading_lock" option (either bool or lock instance) can be used to wrap
				non-threadsafe eventloop polling (can only be done from one thread at a time)
				into a mutex lock, and should only be needed if same-instance methods
				will/should/might be called from different threads at the same time.'''
		self.name = client_name or 'pulsectl'
		self.server, self.connected = server, None
		self._ret = self._ctx = self._loop = self._api = None
		self._actions, self._action_ids = dict(),\
			it.chain.from_iterable(map(range, it.repeat(2**30)))
		self.init()
		if threading_lock:
			if threading_lock is True:
				import threading
				threading_lock = threading.Lock()
			self._loop_lock = threading_lock
		if connect:
			try: self.connect(autospawn=True)
			except PulseError:
				self.close()
				raise

	def init(self):
		self._pa_state_cb = c.PA_STATE_CB_T(self._pulse_state_cb)
		self._pa_subscribe_cb = c.PA_SUBSCRIBE_CB_T(self._pulse_subscribe_cb)

		self._loop, self._loop_lock = c.pa.mainloop_new(), None
		self._loop_running = self._loop_closed = False
		self._api = c.pa.mainloop_get_api(self._loop)

		self._ctx, self._ret = c.pa.context_new(self._api, self.name), c.pa.return_value()
		c.pa.context_set_state_callback(self._ctx, self._pa_state_cb, None)

		c.pa.context_set_subscribe_callback(self._ctx, self._pa_subscribe_cb, None)
		self._pa_subscribe_ev_t = dict(
			(getattr(c, 'PA_SUBSCRIPTION_EVENT_{}'.format(k.upper())), k)
			for k in 'new change remove'.split() )
		self._pa_subscribe_ev_fac, self._pa_subscribe_masks = dict(), dict()
		for k, n in vars(c).items():
			if k.startswith('PA_SUBSCRIPTION_EVENT_'):
				if k.endswith('_MASK'): continue
				k = k[22:].lower()
				if k in self._pa_subscribe_ev_t.values(): continue
				assert n & c.PA_SUBSCRIPTION_EVENT_FACILITY_MASK == n, [k, n]
				self._pa_subscribe_ev_fac[n] = k
			elif k.startswith('PA_SUBSCRIPTION_MASK_'): self._pa_subscribe_masks[k[21:].lower()] = n
		self.event_types = sorted(self._pa_subscribe_ev_t.values())
		self.event_facilities = sorted(self._pa_subscribe_ev_fac.values())
		self.event_masks = sorted(self._pa_subscribe_masks.keys())
		self.event_callback = None

	def connect(self, autospawn=False, wait=False):
		'''Connect to pulseaudio server.
			"autospawn" option will start new pulse daemon, if necessary.
			Specifying "wait" option will make function block until pulseaudio server appears.'''
		if self._loop_closed:
			raise PulseError('Eventloop object was already'
				' destroyed and cannot be reused from this instance.')
		flags, self.connected = 0, None
		if not autospawn: flags |= c.PA_CONTEXT_NOAUTOSPAWN
		if wait: flags |= c.PA_CONTEXT_NOFAIL
		try: c.pa.context_connect(self._ctx, self.server, flags, None)
		except c.pa.CallError: self.connected = False
		while self.connected is None: self._pulse_iterate()
		if self.connected is False: raise PulseError('Failed to connect to pulseaudio server')

	def disconnect(self):
		if not self._ctx or not self.connected: return
		c.pa.context_disconnect(self._ctx)

	def close(self):
		if self._loop:
			if self._loop_running:
				self._loop_closed = True
				c.pa.mainloop_quit(self._loop, 0)
				return
			try:
				self.disconnect()
				c.pa.mainloop_free(self._loop)
			finally: self._ctx = self._loop = None

	def __enter__(self): return self
	def __exit__(self, err_t, err, err_tb): self.close()


	def _pulse_state_cb(self, ctx, userdata):
		state = c.pa.context_get_state(ctx)
		if state >= c.PA_CONTEXT_READY:
			if state == c.PA_CONTEXT_READY: self.connected = True
			elif state in [c.PA_CONTEXT_FAILED, c.PA_CONTEXT_TERMINATED]:
				self.connected, self._loop_stop = False, True
		return 0

	def _pulse_subscribe_cb(self, ctx, ev, idx, userdata):
		if not self.event_callback: return
		n = ev & c.PA_SUBSCRIPTION_EVENT_FACILITY_MASK
		ev_fac = self._pa_subscribe_ev_fac.get(n) or 'ev.facility.{}'.format(n)
		n = ev & c.PA_SUBSCRIPTION_EVENT_TYPE_MASK
		ev_t = self._pa_subscribe_ev_t.get(n) or 'ev.type.{}'.format(n)
		try: self.event_callback(PulseEventInfo(ev_t, ev_fac, idx))
		except PulseLoopStop: self._loop_stop = True

	def _pulse_poll_cb(self, func, func_err, ufds, nfds, timeout, userdata):
		fd_list = list(ufds[n] for n in range(nfds))
		try: nfds = func(fd_list, timeout / 1000.0)
		except Exception as err:
			func_err(*sys.exc_info())
			return -1
		return nfds

	@contextmanager
	def _pulse_loop(self):
		if self._loop_lock: self._loop_lock.acquire()
		try:
			if self._loop_running:
				raise PulseError(
					'Running blocking pulse operations from pulse eventloop callbacks'
						' or other threads while loop is running is not supported by this python module.'
					' Supporting this would require threads or proper asyncio/twisted-like async code.'
					' Workaround can be to stop the loop'
						' (raise PulseLoopStop in callback or event_loop_stop() from another thread),'
						' doing whatever pulse calls synchronously and then resuming event_listen() loop.' )
			self._loop_running, self._loop_stop = True, False
			try: yield self._loop
			finally:
				self._loop_running = False
				if self._loop_closed: self.close() # to free() after stopping it
		finally:
			if self._loop_lock: self._loop_lock.release()

	def _pulse_run(self):
		with self._pulse_loop() as loop: c.pa.mainloop_run(loop, self._ret)

	def _pulse_iterate(self, block=True):
		with self._pulse_loop() as loop: c.pa.mainloop_iterate(loop, int(block), self._ret)

	@contextmanager
	def _pulse_op_cb(self, raw=False):
		act_id = next(self._action_ids)
		self._actions[act_id] = None
		try:
			cb = lambda s=True,k=act_id: self._actions.update({k: bool(s)})
			if not raw: cb = c.PA_CONTEXT_SUCCESS_CB_T(lambda ctx,s,d,cb=cb: cb(s))
			yield cb
			while self._actions[act_id] is None: self._pulse_iterate()
			if not self._actions[act_id]: raise PulseOperationFailed(act_id)
		finally: self._actions.pop(act_id, None)

	def _pulse_poll(self, timeout=None):
		'''timeout should be in seconds (float),
			0 for non-blocking poll and None (default) for no timeout.'''
		with self._pulse_loop() as loop:
			ts = c.mono_time()
			ts_deadline = timeout and (ts + timeout)
			while True:
				delay = max(0, int((ts_deadline - ts) * 1000000)) if ts_deadline else -1
				c.pa.mainloop_prepare(loop, delay) # usec
				c.pa.mainloop_poll(loop)
				if self._loop_closed: break # interrupted by close() or such
				c.pa.mainloop_dispatch(loop)
				if self._loop_stop: break
				ts = c.mono_time()
				if ts_deadline and ts >= ts_deadline: break


	def _pulse_info_cb(self, info_cls, data_list, done_cb, ctx, info, eof, userdata):
		if eof:
			done_cb()
			return 0
		data_list.append(info_cls(info[0]))
		return 0

	def _pulse_get_list(cb_t, pulse_func, info_cls):
		def _wrapper(self, index=None):
			data = list()
			with self._pulse_op_cb(raw=True) as cb:
				cb = cb_t(ft.partial(self._pulse_info_cb, info_cls, data, cb))
				pulse_func(self._ctx, *([index, cb, None] if index is not None else [cb, None]))
			data = data or list()
			if index is not None:
				if not data: raise PulseIndexError(index)
				data, = data
			return _wrapper.func(self, data) if _wrapper.func else data
		_wrapper.func = None
		def _add_wrap_doc(func):
			func.__name__ = '...'
			func.__doc__ = 'Signature: func({})'.format(
				'' if pulse_func.__name__.endswith('_list') else 'index' )
		def _decorator_or_method(func_or_self=None, index=None):
			if func_or_self.__class__.__name__ == 'Pulse':
				return _wrapper(func_or_self, index)
			elif func_or_self: _wrapper.func = func_or_self
			assert index is None, index
			return _wrapper
		_add_wrap_doc(_wrapper)
		_add_wrap_doc(_decorator_or_method)
		return _decorator_or_method

	sink_input_list = _pulse_get_list(
		c.PA_SINK_INPUT_INFO_CB_T,
		c.pa.context_get_sink_input_info_list, PulseSinkInputInfo )
	sink_input_info = _pulse_get_list(
		c.PA_SINK_INPUT_INFO_CB_T,
		c.pa.context_get_sink_input_info, PulseSinkInputInfo )
	source_output_list = _pulse_get_list(
		c.PA_SOURCE_OUTPUT_INFO_CB_T,
		c.pa.context_get_source_output_info_list, PulseSourceOutputInfo )
	source_output_info = _pulse_get_list(
		c.PA_SOURCE_OUTPUT_INFO_CB_T,
		c.pa.context_get_source_output_info, PulseSourceOutputInfo )

	sink_list = _pulse_get_list(
		c.PA_SINK_INFO_CB_T, c.pa.context_get_sink_info_list, PulseSinkInfo )
	sink_info = _pulse_get_list(
		c.PA_SINK_INFO_CB_T, c.pa.context_get_sink_info_by_index, PulseSinkInfo )
	source_list = _pulse_get_list(
		c.PA_SOURCE_INFO_CB_T, c.pa.context_get_source_info_list, PulseSourceInfo )
	source_info = _pulse_get_list(
		c.PA_SOURCE_INFO_CB_T, c.pa.context_get_source_info_by_index, PulseSourceInfo )
	card_list = _pulse_get_list(
		c.PA_CARD_INFO_CB_T, c.pa.context_get_card_info_list, PulseCardInfo )
	card_info = _pulse_get_list(
		c.PA_CARD_INFO_CB_T, c.pa.context_get_card_info_by_index, PulseCardInfo )
	client_list = _pulse_get_list(
		c.PA_CLIENT_INFO_CB_T, c.pa.context_get_client_info_list, PulseClientInfo )
	client_info = _pulse_get_list(
		c.PA_CLIENT_INFO_CB_T, c.pa.context_get_client_info, PulseClientInfo )

	def _pulse_method_call(method_or_func, func=None):
		if func is None: func_method, func = None, method_or_func
		else: func_method = method_or_func
		def _wrapper(self, index, *args, **kws):
			method, pulse_call = func_method, func(*args, **kws)
			if not isinstance(pulse_call, (tuple, list)): pulse_call = [pulse_call]
			if not method: method, pulse_call = pulse_call[0], pulse_call[1:]
			with self._pulse_op_cb() as cb:
				try: method(self._ctx, index, *(list(pulse_call) + [cb, None]))
				except c.pa.CallError as err: raise PulseOperationInvalid(err.args[-1])
		func_args = list(inspect.getargspec(func))
		func_args[0] = ['index'] + list(func_args[0])
		_wrapper.__name__ = '...'
		_wrapper.__doc__ = 'Signature: func' + inspect.formatargspec(*func_args)
		if func.__doc__: _wrapper.__doc__ += '\n\n' + func.__doc__
		return _wrapper

	sink_input_mute = _pulse_method_call(
		c.pa.context_set_sink_input_mute, lambda mute=True: mute )
	sink_input_move = _pulse_method_call(
		c.pa.context_move_sink_input_by_index, lambda sink_index: sink_index )
	sink_mute = _pulse_method_call(
		c.pa.context_set_sink_mute_by_index, lambda mute=True: mute )
	sink_input_volume_set = _pulse_method_call(
		c.pa.context_set_sink_input_volume, lambda vol: vol.to_struct() )
	sink_volume_set = _pulse_method_call(
		c.pa.context_set_sink_volume_by_index, lambda vol: vol.to_struct() )
	sink_suspend = _pulse_method_call(
		c.pa.context_suspend_sink_by_index, lambda suspend=True: suspend )
	sink_port_set = _pulse_method_call(
		c.pa.context_set_sink_port_by_index,
		lambda port: port.name if isinstance(port, PulsePortInfo) else port )

	source_output_mute = _pulse_method_call(
		c.pa.context_set_source_output_mute, lambda mute=True: mute )
	source_output_move = _pulse_method_call(
		c.pa.context_move_source_output_by_index, lambda sink_index: sink_index )
	source_mute = _pulse_method_call(
		c.pa.context_set_source_mute_by_index, lambda mute=True: mute )
	source_output_volume_set = _pulse_method_call(
		c.pa.context_set_source_output_volume, lambda vol: vol.to_struct() )
	source_volume_set = _pulse_method_call(
		c.pa.context_set_source_volume_by_index, lambda vol: vol.to_struct() )
	source_suspend = _pulse_method_call(
		c.pa.context_suspend_source_by_index, lambda suspend=True: suspend )
	source_port_set = _pulse_method_call(
		c.pa.context_set_source_port_by_index,
		lambda port: port.name if isinstance(port, PulsePortInfo) else port )


	def mute(self, obj, mute=True):
		assert isinstance(obj, PulseObject), [type(obj), obj]
		method = {
			PulseSinkInfo: self.sink_mute,
			PulseSinkInputInfo: self.sink_input_mute,
			PulseSourceInfo: self.source_mute,
			PulseSourceOutputInfo: self.source_output_mute }.get(type(obj))
		if not method: raise NotImplementedError(type(obj))
		method(obj.index, mute)
		obj.mute = mute

	def port_set(self, obj, port):
		assert isinstance(obj, PulseObject), [type(obj), obj]
		method = {
			PulseSinkInfo: self.sink_port_set,
			PulseSourceInfo: self.source_port_set }.get(type(obj))
		if not method: raise NotImplementedError(type(obj))
		method(obj.index, port)
		obj.port_active = port

	def volume_set(self, obj, vol):
		assert isinstance(obj, PulseObject), [type(obj), obj]
		method = {
			PulseSinkInfo: self.sink_volume_set,
			PulseSinkInputInfo: self.sink_input_volume_set,
			PulseSourceInfo: self.source_volume_set,
			PulseSourceOutputInfo: self.source_output_volume_set }.get(type(obj))
		if not method: raise NotImplementedError(type(obj))
		method(obj.index, vol)
		obj.volume = vol

	def volume_set_all_chans(self, obj, vol):
		obj.volume.values = [vol for v in obj.volume.values]
		self.volume_set(obj, obj.volume)

	def volume_change_all_chans(self, obj, inc):
		obj.volume.values = [max(0, v + inc) for v in obj.volume.values]
		self.volume_set(obj, obj.volume)

	def volume_get_all_chans(self, obj):
		assert isinstance(obj, PulseObject), [type(obj), obj]
		return sum(obj.volume.values) / len(obj.volume.values)


	def event_mask_set(self, *masks):
		mask = 0
		for m in masks: mask |= self._pa_subscribe_masks[m]
		with self._pulse_op_cb() as cb:
			c.pa.context_subscribe(self._ctx, mask, cb, None)

	def event_callback_set(self, func):
		'''Call event_listen() to start receiving these,
			and be sure to raise PulseLoopStop in a callback to stop the loop.'''
		self.event_callback = func

	def event_listen(self, timeout=None, raise_on_disconnect=True):
		'''Does not return until PulseLoopStop
				gets raised in event callback or timeout passes.
			timeout should be in seconds (float),
				0 for non-blocking poll and None (default) for no timeout.
			raise_on_disconnect causes PulseDisconnected exceptions by default.
			Do not run any pulse operations from these callbacks.'''
		assert self.event_callback
		try: self._pulse_poll(timeout)
		except c.pa.CallError: pass # e.g. from mainloop_dispatch() on disconnect
		if raise_on_disconnect and not self.connected: raise PulseDisconnected()

	def event_listen_stop(self):
		'''Stop event_listen() loop from e.g. another thread.
			Does nothing if libpulse poll is not running yet, so might be racey with
				event_listen() - be sure to call it in a loop until event_listen returns or something.'''
		self._loop_stop = True
		c.pa.mainloop_wakeup(self._loop)


	def set_poll_func(self, func, func_err_handler=None):
		'''Can be used to integrate pulse client into existing eventloop.
			Function will be passed a list of pollfd structs and timeout value (seconds, float),
				which it is responsible to use and modify (set poll flags) accordingly,
				returning int value >= 0 with number of fds that had any new events within timeout.
			func_err_handler defaults to traceback.print_exception(),
				and will be called on any exceptions from callback (to e.g. log these),
				returning poll error code (-1) to libpulse after that.'''
		if not func_err_handler: func_err_handler = traceback.print_exception
		self._pa_poll_cb = c.PA_POLL_FUNC_T(ft.partial(self._pulse_poll_cb, func, func_err_handler))
		c.pa.mainloop_set_poll_func(self._loop, self._pa_poll_cb, None)
