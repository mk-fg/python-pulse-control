# -*- coding: utf-8 -*-
from __future__ import print_function

import itertools as it, operator as op, functools as ft
from collections import defaultdict
import signal

from . import _pulsectl as c


class PulseActionDoneFlag(object):
	def __init__(self): self.state = False
	def set(self, state=True): self.state = state
	def set_callback(self, *args, **kws):
		self.set()
		return 0
	def unset(self): self.state = False
	def __nonzero__(self): return bool(self.state)
	def __repr__(self): return '<PulseActionDoneFlag: {}>'.format(self.state)

class PulseActionDoneFlagAttr(object):
	def __init__(self): self.instances = defaultdict(PulseActionDoneFlag)
	def __get__(self, o, cls): return self.instances[id(o)]
	def __set__(self, o, state): self.instances[id(o)].set(state)
	def __delete__(self, o): self.instances[id(o)].unset()

class PulseError(Exception): pass

class PulseObject(object):

	def __repr__(self):
		return '<{} at {:x} - {}>'.format(self.__class__.__name__, id(self), bytes(self))


class PulsePort(PulseObject):

	def __init__(self, pa_port):
		self.name = pa_port.name
		self.description = pa_port.description
		self.priority = pa_port.priority


class PulseCard(PulseObject):

	def __init__(self, name, index=0):
		self.index = index
		self.name = name

	def __str__(self):
		return 'Card-ID: {}, Name: {}'.format(self.index, self.name)


class PulseCardC(PulseCard):

	def __init__(self, pa_card):
		super(PulseCardC, self).__init__(pa_card.name, pa_card.index)
		self.driver = pa_card.driver
		self.owner_module = pa_card.owner_module
		self.n_profiles = pa_card.n_profiles


class PulseClient(PulseObject):

	def __init__(self, name, index=0):
		self.index = index
		self.name = name

	def __str__(self):
		return 'Client-name: {}'.format(self.name)


class PulseClientC(PulseClient):

	def __init__(self, pa_client):
		super(PulseClientC, self).__init__(pa_client.name, pa_client.index)
		self.driver = pa_client.driver
		self.owner_module = pa_client.owner_module


class PulseSink(PulseObject):

	def __init__(self, index, name, mute, volume, client):
		self.index = index
		self.name = name
		self.mute = mute
		self.volume = volume
		self.client = client


class PulseSinkInfo(PulseSink):

	def __init__(self, pa_sink_info):
		super(PulseSinkInfo, self).__init__(
			pa_sink_info.index,
			pa_sink_info.name,
			pa_sink_info.mute,
			PulseVolumeC(pa_sink_info.volume),
			PulseClient(self.__class__.__name__) )
		self.description = pa_sink_info.description
		self.sample_spec = pa_sink_info.sample_spec
		self.channel_map = pa_sink_info.channel_map
		self.owner_module = pa_sink_info.owner_module
		self.latency = pa_sink_info.latency
		self.driver = pa_sink_info.driver
		self.monitor_source = pa_sink_info.monitor_source
		self.monitor_source_name = pa_sink_info.monitor_source_name
		self.flags = pa_sink_info.flags
		self.proplist = pa_sink_info.proplist
		self.configured_latency = pa_sink_info.configured_latency
		self.n_ports = pa_sink_info.n_ports
		self.ports = [PulsePort(pa_sink_info.ports[i].contents) for i in range(self.n_ports)]
		self.active_port = None
		if self.n_ports: self.active_port = PulsePort(pa_sink_info.active_port.contents)

	def __str__(self):
		return 'ID: {}, Name: {}, Mute: {}, {}'.format(
			self.index, self.description, self.mute, self.volume)


class PulseSinkInputInfo(PulseSink):

	def __init__(self, pa_sink_input_info):
		super(PulseSinkInputInfo, self).__init__(
			pa_sink_input_info.index,
			pa_sink_input_info.name,
			pa_sink_input_info.mute,
			PulseVolumeC(pa_sink_input_info.volume),
			PulseClient(pa_sink_input_info.name) )
		self.owner_module = pa_sink_input_info.owner_module
		self.client_id = pa_sink_input_info.client
		self.sink = pa_sink_input_info.sink
		self.channel_map = pa_sink_input_info.channel_map
		self.sample_spec = pa_sink_input_info.sample_spec
		self.buffer_usec = pa_sink_input_info.buffer_usec
		self.sink_usec = pa_sink_input_info.sink_usec
		self.resample_method = pa_sink_input_info.resample_method
		self.driver = pa_sink_input_info.driver

	def __str__(self):
		if self.client:
			return 'ID: {}, Name: {}, Mute: {}, {}'.format(
				self.index, self.client.name, self.mute, self.volume)
		return 'ID: {}, Name: {}, Mute: {}'.format(
			self.index, self.name, self.mute)


class PulseSource(PulseObject):

	def __init__(self, index, name, mute, volume, client):
		self.index = index
		self.name = name
		self.mute = mute
		self.client = client
		self.volume = volume


class PulseSourceInfo(PulseSource):

	def __init__(self, pa_source_info):
		super(PulseSourceInfo, self).__init__(
			pa_source_info.index,
			pa_source_info.name,
			pa_source_info.mute,
			PulseVolumeC(pa_source_info.volume),
			PulseClient(self.__class__.__name__) )
		self.description = pa_source_info.description
		self.sample_spec = pa_source_info.sample_spec
		self.channel_map = pa_source_info.channel_map
		self.owner_module = pa_source_info.owner_module
		self.monitor_of_sink = pa_source_info.monitor_of_sink
		self.monitor_of_sink_name = pa_source_info.monitor_of_sink_name
		self.latency = pa_source_info.latency
		self.driver = pa_source_info.driver
		self.flags = pa_source_info.flags
		self.proplist = pa_source_info.proplist
		self.configured_latency = pa_source_info.configured_latency
		self.n_ports = pa_source_info.n_ports
		self.ports = [PulsePort(pa_source_info.ports[i].contents) for i in range(self.n_ports)]
		self.active_port = None
		if self.n_ports: self.active_port = PulsePort(pa_source_info.active_port.contents)

	def __str__(self):
		return 'ID: {}, Name: {}, Mute: {}, {}'.format(
			self.index, self.description, self.mute, self.volume)


class PulseSourceOutputInfo(PulseSource):

	def __init__(self, pa_source_output_info):
		super(PulseSourceOutputInfo, self).__init__(
			pa_source_output_info.index,
			pa_source_output_info.name,
			pa_source_output_info.mute,
			PulseVolumeC(pa_source_output_info.volume),
			PulseClient(pa_source_output_info.name) )
		self.owner_module = pa_source_output_info.owner_module
		self.client_id = pa_source_output_info.client
		self.source = pa_source_output_info.source
		self.sample_spec = pa_source_output_info.sample_spec
		self.channel_map = pa_source_output_info.channel_map
		self.buffer_usec = pa_source_output_info.buffer_usec
		self.source_usec = pa_source_output_info.source_usec
		self.resample_method = pa_source_output_info.resample_method
		self.driver = pa_source_output_info.driver

	def __str__(self):
		if self.client:
			return 'ID: {}, Name: {}, Mute: {}, {}'.format(
				self.index, self.client.name, self.mute, self.volume)
		return 'ID: {}, Name: {}, Mute: {}'.format(
			self.index, self.name, self.mute)


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
		return 'Channels: {}, Volumes: {}'.format(
			self.channels, [str(x) + '%' for x in self.values])


class PulseVolumeC(PulseVolume):

	def __init__(self, cvolume):
		self.channels = cvolume.channels
		self.values = [(round(x * 100 / c.PA_VOLUME_NORM)) for x in cvolume.values[:self.channels]]


class Pulse(object):

	action_done = PulseActionDoneFlagAttr()

	def __init__(self, client_name=None, server=None, retry=True):
		self.name = client_name or 'pulsectl'
		self.server, self.retry, self.connected = server, retry, False
		self._ret = self._ctx = self._op = self._loop = self._api = None
		self._data = list()
		self.init()

	def init(self):
		self.pa_signal_cb = c.PA_SIGNAL_CB_T(self._pulse_signal_cb)
		self.pa_state_cb = c.PA_STATE_CB_T(self._pulse_state_cb)

		self._loop = c.pa_mainloop_new()
		self._api = c.pa_mainloop_get_api(self._loop)

		if c.pa_signal_init(self._api) != 0:
			raise PulseError('pa_signal_init failed')

		c.pa_signal_new(2, self.pa_signal_cb, None)
		c.pa_signal_new(15, self.pa_signal_cb, None)

		self._ctx = c.pa_context_new(self._api, self.name)
		c.pa_context_set_state_callback(self._ctx, self.pa_state_cb, None)
		self.action_done = False

		if c.pa_context_connect(self._ctx, self.server, 0, None) < 0:
			if self.retry:
				c.pa_context_disconnect(self._ctx)
				return
			self.close()
		self._pulse_iterate()

	def close(self):
		if self._loop:
			if self._ctx:
				c.pa_context_disconnect(self._ctx)
				self._ctx = None
			c.pa_mainloop_quit(self._loop, 0)
			c.pa_signal_done()
			c.pa_mainloop_free(self._loop)
			self._loop = None

	def reconnect(self):
		self._ctx = c.pa_context_new(self._api, self.name)
		c.pa_context_set_state_callback(self._ctx, self.pa_state_cb, None)
		self.action_done = False
		if c.pa_context_connect(self._ctx, self.server, 0, None) < 0:
			if self.retry:
				c.pa_context_disconnect(self._ctx)
				return
			self.close()
		self._pulse_iterate()

	def __enter__(self): return self
	def __exit__(self, err_t, err, err_tb): self.close()


	def _pulse_signal_cb(self, api, e, sig, userdata):
		if sig in [signal.SIGINT, signal.SIGTERM]: self.close()
		return 0

	def _pulse_state_cb(self, ctx, b):
		state = c.pa_context_get_state(ctx)
		if state in [4, 5, 6]:
			if state == 6:
				if not self.retry: self.close() # XXX
			elif state == 4: self.connected = True
			elif state == 5: self.connected = False
			self.action_done = True
		return 0

	def _pulse_run(self):
		self._ret = c.pa_return_value()
		c.pa_mainloop_run(self._loop, self._ret)

	def _pulse_iterate(self, block=True):
		self._ret = c.pa_return_value()
		c.pa_mainloop_iterate(self._loop, int(block), self._ret)
		while not self.action_done:
			c.pa_mainloop_iterate(self._loop, int(block), self._ret)


	def _pulse_info_cb(self, info_cls, ctx, info, eof, userdata):
		if eof:
			self.action_done = True
			return 0
		self._data.append(info_cls(info[0]))
		return 0

	def _pulse_get_list(cb_t, pulse_func, info_cls):
		def _wrapper(self):
			self.action_done = False
			CB = cb_t(ft.partial(self._pulse_info_cb, info_cls))
			self._op = pulse_func(self._ctx, CB, None)
			self._pulse_iterate()
			assert self.action_done
			data = list(self._data)
			del self._data[:]
			return _wrapper.func(self, data or list()) if _wrapper.func else data
		_wrapper.func = None
		def _decorator_or_method(func_or_self=None):
			if func_or_self.__class__.__name__ == 'Pulse': return _wrapper(func_or_self)
			elif func_or_self:
				_wrapper.func = func_or_self
				return ft.wraps(func_or_self)(_wrapper)
			return _wrapper
		return _decorator_or_method

	def _pulse_fill_clients(self, data):
		if not data: return list()
		clist = self.client_list()
		for d in data:
			for c in clist:
				if c.index == d.client_id:
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
		c.PA_CARD_INFO_CB_T, c.pa_context_get_card_info_list, PulseCardC )
	client_list = _pulse_get_list(
		c.PA_CLIENT_INFO_CB_T, c.pa_context_get_client_info_list, PulseClientC )


	def _pulse_method_call(method_or_func, func=None):
		if func is None: func_method, func = None, method_or_func
		else: func_method = method_or_func
		@ft.wraps(func)
		def _wrapper(self, index, *args, **kws):
			method, pulse_call = func_method, func(*args, **kws)
			if not isinstance(pulse_call, (tuple, list)): pulse_call = [pulse_call]
			if not method: method, pulse_call = pulse_call[0], pulse_call[1:]
			self.action_done = False
			CONTEXT = c.PA_CONTEXT_SUCCESS_CB_T(self.action_done.set_callback)
			self._op = method(self._ctx, index, *(list(pulse_call) + [CONTEXT, None]))
			self._pulse_iterate()
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
