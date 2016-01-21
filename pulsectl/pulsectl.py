# -*- coding: utf-8 -*-
from __future__ import print_function

import itertools as it, operator as op, functools as ft
from collections import defaultdict
from contextlib import contextmanager
import inspect, signal

from . import _pulsectl as c


class PulseError(Exception): pass
class PulseOperationFailed(PulseError): pass

class PulseLoopStop(Exception): pass

class PulseObject(object):

	def __init__(self, struct=None, *field_data_list, **field_data_dict):
		field_data, fields = dict(), getattr(self, 'c_struct_fields', list())
		if isinstance(fields, bytes): fields = self.c_struct_fields = fields.split()
		if field_data_list: field_data.update(zip(fields, field_data_list))
		if field_data_dict: field_data.update(field_data_dict)
		if struct is None: field_data, struct = dict(), field_data
		assert not set(field_data.keys()).difference(fields)
		self._copy_struct_fields(field_data, fields=field_data.keys())
		self._copy_struct_fields(struct, fields=set(fields).difference(field_data.keys()))

	def _copy_struct_fields(self, struct, fields=None):
		if not fields: fields = self.c_struct_fields
		for k in fields:
			setattr(self, k, getattr(struct, k) if not isinstance(struct, dict) else struct[k])

	def _as_str(self, ext=None, fields=None, **kws):
		kws = list(it.starmap('{}={!r}'.format, kws.viewitems()))
		if fields:
			if isinstance(fields, bytes): fields = fields.split()
			kws.extend('{}={!r}'.format(k, getattr(self, k)) for k in fields)
		kws = sorted(kws)
		if ext: kws.append(bytes(ext))
		return ', '.join(kws)

	def __str__(self):
		return self._as_str(fields=self.c_struct_fields)

	def __repr__(self):
		return '<{} at {:x} - {}>'.format(self.__class__.__name__, id(self), bytes(self))


class PulsePort(PulseObject):
	c_struct_fields = 'name description priority'

class PulseCard(PulseObject):
	c_struct_fields = 'name index driver owner_module n_profiles'

class PulseClient(PulseObject):
	c_struct_fields = 'name index driver owner_module'

class PulseSink(PulseObject):
	c_struct_fields = 'index name mute volume client'

class PulseSinkInfo(PulseObject):
	c_struct_fields = ( 'index name mute volume'
		' description sample_spec channel_map owner_module latency driver monitor_source'
		' monitor_source_name flags proplist configured_latency n_ports ports active_port' )

	def __init__(self, pa_sink_info):
		super(PulseSinkInfo, self).__init__(
			pa_sink_info,
			volume=PulseVolumeC(pa_sink_info.volume),
			ports=list(
				PulsePort(pa_sink_info.ports[n].contents)
				for n in xrange(pa_sink_info.n_ports) ),
			active_port=PulsePort(pa_sink_info.active_port.contents)
				if pa_sink_info.n_ports else None )

	def __str__(self):
		return self._as_str(self.volume, fields='index name description mute')

class PulseSinkInputInfo(PulseObject):
	c_struct_fields = ( 'index name mute volume client'
		' owner_module sink channel_map sample_spec'
		' buffer_usec sink_usec resample_method driver' )

	def __init__(self, pa_sink_input_info):
		super(PulseSinkInputInfo, self).__init__(
			pa_sink_input_info,
			volume=PulseVolumeC(pa_sink_input_info.volume) )

	def __str__(self):
		return self._as_str(fields='index name mute')

class PulseSource(PulseObject):
	c_struct_fields = 'index name mute volume client'

class PulseSourceInfo(PulseObject):
	c_struct_fields = ( 'index name mute volume'
		' description sample_spec channel_map owner_module latency driver monitor_of_sink'
		' monitor_of_sink_name flags proplist configured_latency n_ports ports active_port' )

	def __init__(self, pa_source_info):
		super(PulseSourceInfo, self).__init__(
			pa_source_info,
			volume=PulseVolumeC(pa_source_info.volume),
			ports=list(
				PulsePort(pa_source_info.ports[n].contents)
				for n in xrange(pa_source_info.n_ports) ),
			active_port=PulsePort(pa_source_info.active_port.contents)
				if pa_source_info.n_ports else None )

	def __str__(self):
		return self._as_str(self.volume, fields='index name description mute')

class PulseSourceOutputInfo(PulseObject):
	c_struct_fields = ( 'index name mute volume client'
		' owner_module source channel_map sample_spec'
		' buffer_usec source_usec resample_method driver' )

	def __init__(self, pa_source_output_info):
		super(PulseSourceOutputInfo, self).__init__(
			pa_source_output_info,
			volume=PulseVolumeC(pa_source_output_info.volume) )

	def __str__(self):
		return self._as_str(fields='index name mute')

class PulseVolume(PulseObject):

	def __init__(self, values=0, channels=2):
		values = max(min(values, 150), 0)
		self.channels = channels
		self.values = [values] * self.channels

	def to_c(self):
		self.values = list(map(lambda x: max(min(x, 150), 0), self.values))
		cvolume = c.PA_CVOLUME()
		cvolume.channels = self.channels
		for x in range(self.channels):
			cvolume.values[x] = int(round((self.values[x] * c.PA_VOLUME_NORM) / 100))
		return cvolume

	def __str__(self):
		return self._as_str(channels=self.channels, volumes=' / '.join(map('{}%'.format, self.values)))

class PulseVolumeC(PulseVolume):

	def __init__(self, cvolume):
		self.channels = cvolume.channels
		self.values = [(round(x * 100 / c.PA_VOLUME_NORM)) for x in cvolume.values[:self.channels]]

class PulseEventInfo(PulseObject):

	def __init__(self, ev_t, facility, idx):
		self.t, self.facility, self.idx = ev_t, facility, idx

	def __str__(self):
		return self._as_str(fields='t facility idx'.split())


class Pulse(object):

	def __init__(self, client_name=None, server=None):
		self.name = client_name or 'pulsectl'
		self.server, self.connected = server, None
		self._ret = self._ctx = self._loop = self._api = None
		self._actions, self._action_ids = dict(),\
			it.chain.from_iterable(it.imap(xrange, it.repeat(2**30)))
		self.init()

	def init(self):
		self._pa_signal_cb = c.PA_SIGNAL_CB_T(self._pulse_signal_cb)
		self._pa_state_cb = c.PA_STATE_CB_T(self._pulse_state_cb)
		self._pa_subscribe_cb = c.PA_SUBSCRIBE_CB_T(self._pulse_subscribe_cb)

		self._loop = c.pa_mainloop_new()
		self._loop_running = self._loop_close = False
		self._api = c.pa_mainloop_get_api(self._loop)

		if c.pa_signal_init(self._api) != 0:
			raise PulseError('pa_signal_init failed')

		c.pa_signal_new(2, self._pa_signal_cb, None)
		c.pa_signal_new(15, self._pa_signal_cb, None)

		self._ctx, self._ret = c.pa_context_new(self._api, self.name), c.pa_return_value()
		c.pa_context_set_state_callback(self._ctx, self._pa_state_cb, None)

		c.pa_context_set_subscribe_callback(self._ctx, self._pa_subscribe_cb, None)
		self._pa_subscribe_ev_t = dict(
			(getattr(c, 'PA_SUBSCRIPTION_EVENT_{}'.format(k.upper())), k)
			for k in 'new change remove'.split() )
		self._pa_subscribe_ev_fac, self._pa_subscribe_masks = dict(), dict()
		for k, n in vars(c).viewitems():
			if k.startswith('PA_SUBSCRIPTION_EVENT_'):
				if k.endswith('_MASK'): continue
				k = k[22:].lower()
				if k in self._pa_subscribe_ev_t.values(): continue
				assert n & c.PA_SUBSCRIPTION_EVENT_FACILITY_MASK == n, [k, n]
				self._pa_subscribe_ev_fac[n] = k
			elif k.startswith('PA_SUBSCRIPTION_MASK_'): self._pa_subscribe_masks[k[21:].lower()] = n
		self.event_types = sorted(self._pa_subscribe_ev_t.viewvalues())
		self.event_facilities = sorted(self._pa_subscribe_ev_fac.viewvalues())
		self.event_masks = sorted(self._pa_subscribe_masks.keys())
		self.event_callback = None

		if c.pa_context_connect(self._ctx, self.server, 0, None) < 0:
			self.close()
			raise PulseError('pa_context_connect failed')
		while self.connected is None: self._pulse_iterate()

	def close(self):
		if self._loop:
			if self._loop_running:
				c.pa_mainloop_quit(self._loop, 0)
				self._loop_close = True
				return
			try:
				if self._ctx: c.pa_context_disconnect(self._ctx)
				c.pa_signal_done()
				c.pa_mainloop_free(self._loop)
			finally: self._ctx = self._loop = None

	def __enter__(self): return self
	def __exit__(self, err_t, err, err_tb): self.close()


	def _pulse_signal_cb(self, api, e, sig, userdata):
		if sig in [signal.SIGINT, signal.SIGTERM]: self.close()
		return 0

	def _pulse_state_cb(self, ctx, userdata):
		state = c.pa_context_get_state(ctx)
		if state >= c.PA_CONTEXT_READY:
			if state == c.PA_CONTEXT_READY: self.connected = True
			elif state == c.PA_CONTEXT_FAILED: self.connected = False
			# c.PA_CONTEXT_TERMINATED also happens here on clean disconnect
		return 0

	def _pulse_subscribe_cb(self, ctx, ev, idx, userdata):
		if not self.event_callback: return
		ev_fac = self._pa_subscribe_ev_fac[
			ev & c.PA_SUBSCRIPTION_EVENT_FACILITY_MASK ]
		ev_t = self._pa_subscribe_ev_t[ev & c.PA_SUBSCRIPTION_EVENT_TYPE_MASK]
		try: self.event_callback(PulseEventInfo(ev_t, ev_fac, idx))
		except PulseLoopStop: c.pa_mainloop_quit(self._loop, 0)

	@contextmanager
	def _pulse_loop(self):
		self._loop_running = True
		try: yield self._loop
		finally:
			self._loop_running = False
			if self._loop_close: self.close()

	def _pulse_run(self):
		with self._pulse_loop() as loop: c.pa_mainloop_run(loop, self._ret)

	def _pulse_iterate(self, block=True):
		with self._pulse_loop() as loop: c.pa_mainloop_iterate(loop, int(block), self._ret)

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
		if timeout is None: timeout = -1
		with self._pulse_loop() as loop:
			ts = c.mono_time()
			ts_deadline = ts + timeout
			while True:
				delay = max(0, int((ts_deadline - ts) * 1000000))
				try:
					c.pa_mainloop_prepare(loop, delay) # usec
					c.pa_mainloop_poll(loop)
					c.pa_mainloop_dispatch(loop)
				except c.ResCheckError as err:
					if err.args[1] == -2: break # indicates stopped loop
					raise
				ts = c.mono_time()
				if ts >= ts_deadline: break


	def _pulse_info_cb(self, info_cls, data_list, done_cb, ctx, info, eof, userdata):
		if eof:
			done_cb()
			return 0
		data_list.append(info_cls(info[0]))
		return 0

	def _pulse_get_list(cb_t, pulse_func, info_cls):
		def _wrapper(self):
			data = list()
			with self._pulse_op_cb(raw=True) as cb:
				cb = cb_t(ft.partial(self._pulse_info_cb, info_cls, data, cb))
				pulse_func(self._ctx, cb, None)
			return _wrapper.func(self, data or list()) if _wrapper.func else data
		_wrapper.func = None
		def _add_wrap_doc(func):
			func.func_name = '...'
			func.func_doc = 'Signature: func()'
			return func
		def _decorator_or_method(func_or_self=None):
			if func_or_self.__class__.__name__ == 'Pulse': return _wrapper(func_or_self)
			elif func_or_self: _wrapper.func = func_or_self
			return _wrapper
		_add_wrap_doc(_wrapper)
		_add_wrap_doc(_decorator_or_method)
		return _decorator_or_method

	def _pulse_fill_clients(self, data):
		if not data: return list()
		clist = self.client_list()
		for d in data:
			for c in clist:
				if c.index == d.client:
					d.client = c
					break
		return data

	sink_input_list = _pulse_get_list(
		c.PA_SINK_INPUT_INFO_CB_T,
		c.pa_context_get_sink_input_info_list, PulseSinkInputInfo )(_pulse_fill_clients)
	source_output_list = _pulse_get_list(
		c.PA_SOURCE_OUTPUT_INFO_CB_T,
		c.pa_context_get_source_output_info_list, PulseSourceOutputInfo )(_pulse_fill_clients)

	sink_list = _pulse_get_list(
		c.PA_SINK_INFO_CB_T, c.pa_context_get_sink_info_list, PulseSinkInfo )
	source_list = _pulse_get_list(
		c.PA_SOURCE_INFO_CB_T, c.pa_context_get_source_info_list, PulseSourceInfo )
	card_list = _pulse_get_list(
		c.PA_CARD_INFO_CB_T, c.pa_context_get_card_info_list, PulseCard )
	client_list = _pulse_get_list(
		c.PA_CLIENT_INFO_CB_T, c.pa_context_get_client_info_list, PulseClient )


	def _pulse_method_call(method_or_func, func=None):
		if func is None: func_method, func = None, method_or_func
		else: func_method = method_or_func
		def _wrapper(self, index, *args, **kws):
			method, pulse_call = func_method, func(*args, **kws)
			if not isinstance(pulse_call, (tuple, list)): pulse_call = [pulse_call]
			if not method: method, pulse_call = pulse_call[0], pulse_call[1:]
			with self._pulse_op_cb() as cb:
				method(self._ctx, index, *(list(pulse_call) + [cb, None]))
		func_args = list(inspect.getargspec(func))
		func_args[0] = ['index'] + list(func_args[0])
		_wrapper.func_name = '...'
		_wrapper.func_doc = 'Signature: func' + inspect.formatargspec(*func_args)
		if func.func_doc: _wrapper.func_doc += '\n\n' + func.func_doc
		return _wrapper

	sink_input_mute = _pulse_method_call(
		c.pa_context_set_sink_input_mute, lambda mute=True: mute )
	sink_input_move = _pulse_method_call(
		c.pa_context_move_sink_input_by_index, lambda sink_index: sink_index )
	sink_mute = _pulse_method_call(
		c.pa_context_set_sink_mute_by_index, lambda mute=True: mute )
	sink_input_volume_set = _pulse_method_call(
		c.pa_context_set_sink_input_volume, lambda vol: vol.to_c() )
	sink_volume_set = _pulse_method_call(
		c.pa_context_set_sink_volume_by_index, lambda vol: vol.to_c() )
	sink_suspend = _pulse_method_call(
		c.pa_context_suspend_sink_by_index, lambda suspend=True: suspend )
	sink_port_set = _pulse_method_call(
		c.pa_context_set_sink_port_by_index, lambda port: port )

	source_output_mute = _pulse_method_call(
		c.pa_context_set_source_output_mute, lambda mute=True: mute )
	source_output_move = _pulse_method_call(
		c.pa_context_move_source_output_by_index, lambda sink_index: sink_index )
	source_mute = _pulse_method_call(
		c.pa_context_set_source_mute_by_index, lambda mute=True: mute )
	source_output_volume_set = _pulse_method_call(
		c.pa_context_set_source_output_volume, lambda vol: vol.to_c() )
	source_volume_set = _pulse_method_call(
		c.pa_context_set_source_volume_by_index, lambda vol: vol.to_c() )
	source_suspend = _pulse_method_call(
		c.pa_context_suspend_source_by_index, lambda suspend=True: suspend )
	source_port_set = _pulse_method_call(
		c.pa_context_set_source_port_by_index, lambda port: port )


	def mute(self, obj, mute=True):
		assert isinstance(obj, PulseObject), [type(obj), obj]
		method = {
			PulseSinkInfo: self.sink_mute,
			PulseSinkInputInfo: self.source_mute,
			PulseSourceInfo: self.source_mute,
			PulseSourceOutputInfo: self.source_output_mute }.get(type(obj))
		if not method: raise NotImplementedError(type(obj))
		method(obj.index, mute)
		obj.mute = mute

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
		obj.volume.values = [v + inc for v in obj.volume.values]
		self.volume_set(obj, obj.volume)

	def volume_get_all_chans(self, obj):
		assert isinstance(obj, PulseObject), [type(obj), obj]
		return int(sum(obj.volume.values) / len(obj.volume.values))


	def event_mask_set(self, *masks):
		mask = 0
		for m in masks: mask |= self._pa_subscribe_masks[m]
		with self._pulse_op_cb() as cb:
			c.pa_context_subscribe(self._ctx, mask, cb, None)

	def event_callback_set(self, func):
		'''Call event_listen() to start receiving these,
			and be sure to raise PulseLoopStop in a callback to stop the loop.'''
		self.event_callback = func

	def event_listen(self, timeout=None):
		'''Does not return until PulseLoopStop
				gets raised in event callback or timeout passes.
			timeout should be in seconds (float),
				0 for non-blocking poll and None (default) for no timeout.'''
		assert self.event_callback
		self._pulse_poll(timeout)
