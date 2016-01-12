# -*- coding: utf-8 -*-
from __future__ import print_function

from . import _pulsectl as c


class PulseError(Exception): pass


class PulsePort(object):

	def __init__(self, pa_port):
		self.name = pa_port.name
		self.description = pa_port.description
		self.priority = pa_port.priority


class PulseCard(object):

	def __init__(self, name, index=0):
		self.index = index
		self.name = name

	def __str__(self):
		return 'Card-ID: {}, Name: {}'.format(self.index, self.name)


class PulseCardC(PulseCard):

	def __init__(self, pa_card):
		PulseCard.__init__(self, pa_card.name, pa_card.index)
		self.driver = pa_card.driver
		self.owner_module = pa_card.owner_module
		self.n_profiles = pa_card.n_profiles


class PulseClient(object):

	def __init__(self, name, index=0):
		self.index = index
		self.name = name

	def __str__(self):
		return 'Client-name: {}'.format(self.name)


class PulseClientC(PulseClient):

	def __init__(self, pa_client):
		PulseClient.__init__(self, pa_client.name, pa_client.index)
		self.driver = pa_client.driver
		self.owner_module = pa_client.owner_module


class Pulse(object):

	def __init__(self, client_name=None, server=None, retry=False):
		self.server = server
		self.ret = None
		self.retry = retry
		self.context = None
		self.operation = None
		self.connected = False
		self.action_done = False
		self.data = []
		self.mainloop = None
		self.mainloop_api = None
		self.client_name = (client_name or 'pulsectl')

		self.pa_signal_cb = c.PA_SIGNAL_CB_T(self.signal_cb)
		self.pa_state_cb = c.PA_STATE_CB_T(self.state_cb)

		self.mainloop = c.pa_mainloop_new()
		self.mainloop_api = c.pa_mainloop_get_api(self.mainloop)

		if c.pa_signal_init(self.mainloop_api) != 0:
			raise PulseError('pa_signal_init failed')

		c.pa_signal_new(2, self.pa_signal_cb, None)
		c.pa_signal_new(15, self.pa_signal_cb, None)

		self.context = c.pa_context_new(self.mainloop_api, self.client_name)
		c.pa_context_set_state_callback(self.context, self.pa_state_cb, None)
		self.start_action()

		if c.pa_context_connect(self.context, self.server, 0, None) < 0:
			if self.retry:
				c.pa_context_disconnect(self.context)
				return
			self.pulse_context_error()
		self.pulse_iterate()

	def unmute_stream(self, obj):
		if type(obj) is PulseSinkInfo:
			self.pulse_sink_mute(obj.index, 0)
		elif type(obj) is PulseSinkInputInfo:
			self.pulse_sink_input_mute(obj.index, 0)
		elif type(obj) is PulseSourceInfo:
			self.pulse_source_mute(obj.index, 0)
		elif type(obj) is PulseSourceOutputInfo:
			self.pulse_source_output_mute(obj.index, 0)
		else:
			raise NotImplementedError(type(obj))
		obj.mute = 0

	def mute_stream(self, obj):
		if type(obj) is PulseSinkInfo:
			self.pulse_sink_mute(obj.index, 1)
		elif type(obj) is PulseSinkInputInfo:
			self.pulse_sink_input_mute(obj.index, 1)
		elif type(obj) is PulseSourceInfo:
			self.pulse_source_mute(obj.index, 1)
		elif type(obj) is PulseSourceOutputInfo:
			self.pulse_source_output_mute(obj.index, 1)
		else:
			raise NotImplementedError(type(obj))
		obj.mute = 1

	def set_volume(self, obj, volume):
		if type(obj) is PulseSinkInfo:
			self.pulse_set_sink_volume(obj.index, volume)
		elif type(obj) is PulseSinkInputInfo:
			self.pulse_set_sink_input_volume(obj.index, volume)
		elif type(obj) is PulseSourceInfo:
			self.pulse_set_source_volume(obj.index, volume)
		elif type(obj) is PulseSourceOutputInfo:
			self.pulse_set_source_output_volume(obj.index, volume)
		else:
			raise NotImplementedError(type(obj))
		obj.volume = volume

	def change_volume_mono(self, obj, inc):
		obj.volume.values = [v + inc for v in obj.volume.values]
		self.set_volume(obj, obj.volume)

	def get_volume_mono(self, obj):
		return int(sum(obj.volume.values) / len(obj.volume.values))

	def fill_clients(self):
		if not self.data: return
		data, self.data = self.data, []
		clist = self.pulse_client_list()
		for d in data:
			for c in clist:
				if c.index == d.client_id:
					d.client = c
					break
		return data

	def signal_cb(self, api, e, sig, userdata):
		if sig == 2 or sig == 15: self.pulse_disconnect()
		return 0

	def state_cb(self, c, b):
		state = c.pa_context_get_state(c)
		if state == 4:
			self.complete_action()
			self.connected = True
		elif state == 5:
			self.connected = False
			self.complete_action()
		elif state == 6:
			if not self.retry: raise PulseError(c.pa_context_errno(c))
			self.complete_action()
		return 0

	def _cb(func):
		def wrapper(self, c, info, eof, userdata):
			if eof:
				self.complete_action()
				return 0
			func(self, c, info, eof, userdata)
			return 0
		return wrapper

	@_cb
	def card_cb(self, c, card_info, eof, userdata):
		self.data.append(PulseCardC(card_info[0]))

	@_cb
	def client_cb(self, c, client_info, eof, userdata):
		self.data.append(PulseClientC(client_info[0]))

	@_cb
	def sink_input_cb(self, c, sink_input_info, eof, userdata):
		self.data.append(PulseSinkInputInfo(sink_input_info[0]))

	@_cb
	def sink_cb(self, c, sink_info, eof, userdata):
		self.data.append(PulseSinkInfo(sink_info[0]))

	@_cb
	def source_output_cb(self, c, source_output_info, eof, userdata):
		self.data.append(PulseSourceOutputInfo(source_output_info[0]))

	@_cb
	def source_cb(self, c, source_info, eof, userdata):
		self.data.append(PulseSourceInfo(source_info[0]))

	def context_success(self, c, success, userdata):
		self.complete_action()
		return 0

	def complete_action(self):
		self.action_done = True

	def start_action(self):
		self.action_done = False

	def pulse_disconnect(self):
		c.pa_context_disconnect(self.context)
		c.pa_mainloop_free(self.mainloop)

	def pulse_context_error(self):
		self.pulse_disconnect()

	def pulse_sink_input_list(self):
		self.start_action()
		CB = c.PA_SINK_INPUT_INFO_CB_T(self.sink_input_cb)
		self.operation = c.pa_context_get_sink_input_info_list(self.context, CB, None)
		self.pulse_iterate()
		data, self.data = self.fill_clients(), []
		return data or []

	def pulse_sink_list(self):
		self.start_action()
		CB = c.PA_SINK_INFO_CB_T(self.sink_cb)
		self.operation = c.pa_context_get_sink_info_list(self.context, CB, None)
		self.pulse_iterate()
		data, self.data = self.data, []
		return data or []

	def pulse_source_output_list(self):
		self.start_action()
		CB = c.PA_SOURCE_OUTPUT_INFO_CB_T(self.source_output_cb)
		self.operation = c.pa_context_get_source_output_info_list(self.context, CB, None)
		self.pulse_iterate()
		data, self.data = self.fill_clients(), []
		return data or []

	def pulse_source_list(self):
		self.start_action()
		CB = c.PA_SOURCE_INFO_CB_T(self.source_cb)
		self.operation = c.pa_context_get_source_info_list(self.context, CB, None)
		self.pulse_iterate()
		data, self.data = self.data, []
		return data or []

	def pulse_card_list(self):
		self.start_action()
		CB = c.PA_CARD_INFO_CB_T(self.card_cb)
		self.operation = c.pa_context_get_card_info_list(self.context, CB, None)
		self.pulse_iterate()
		data, self.data = self.data, []
		return data or []

	def pulse_client_list(self):
		self.start_action()
		CB = c.PA_CLIENT_INFO_CB_T(self.client_cb)
		self.operation = c.pa_context_get_client_info_list(self.context, CB, None)
		self.pulse_iterate()
		data, self.data = self.data, []
		return data or []

	def pulse_sink_input_mute(self, index, mute):
		self.start_action()
		CONTEXT = c.PA_CONTEXT_SUCCESS_CB_T(self.context_success)
		self.operation = c.pa_context_set_sink_input_mute(self.context,
			index, mute,
			CONTEXT, None)
		self.pulse_iterate()

	def pulse_sink_input_move(self, index, sink_index):
		self.start_action()
		CONTEXT = c.PA_CONTEXT_SUCCESS_CB_T(self.context_success)
		self.operation = c.pa_context_move_sink_input_by_index(self.context,
			index, sink_index,
			CONTEXT, None)
		self.pulse_iterate()

	def pulse_sink_mute(self, index, mute):
		self.start_action()
		CONTEXT = c.PA_CONTEXT_SUCCESS_CB_T(self.context_success)
		self.operation = c.pa_context_set_sink_mute_by_index(self.context,
			index, mute,
			CONTEXT, None)
		self.pulse_iterate()

	def pulse_set_sink_input_volume(self, index, vol):
		self.start_action()
		CONTEXT = c.PA_CONTEXT_SUCCESS_CB_T(self.context_success)
		self.operation = c.pa_context_set_sink_input_volume(self.context,
			index, vol.to_c(),
			CONTEXT, None)
		self.pulse_iterate()

	def pulse_set_sink_volume(self, index, vol):
		self.start_action()
		CONTEXT = c.PA_CONTEXT_SUCCESS_CB_T(self.context_success)
		self.operation = c.pa_context_set_sink_volume_by_index(self.context,
			index, vol.to_c(),
			CONTEXT, None)
		self.pulse_iterate()

	def pulse_sink_suspend(self, index, suspend):
		self.start_action()
		CONTEXT = c.PA_CONTEXT_SUCCESS_CB_T(self.context_success)
		self.operation = c.pa_context_suspend_sink_by_index(self.context,
			index, suspend,
			CONTEXT, None)
		self.pulse_iterate()

	def pulse_set_sink_port(self, index, port):
		self.start_action()
		CONTEXT = c.PA_CONTEXT_SUCCESS_CB_T(self.context_success)
		self.operation = c.pa_context_set_sink_port_by_index(self.context,
			index, port,
			CONTEXT, None)
		self.pulse_iterate()

	def pulse_set_source_output_volume(self, index, vol):
		self.start_action()
		CONTEXT = c.PA_CONTEXT_SUCCESS_CB_T(self.context_success)
		self.operation = c.pa_context_set_source_output_volume(self.context,
			index, vol.to_c(),
			CONTEXT, None)
		self.pulse_iterate()

	def pulse_set_source_volume(self, index, vol):
		self.start_action()
		CONTEXT = c.PA_CONTEXT_SUCCESS_CB_T(self.context_success)
		self.operation = c.pa_context_set_source_volume_by_index(self.context,
			index, vol.to_c(),
			CONTEXT, None)
		self.pulse_iterate()

	def pulse_source_suspend(self, index, suspend):
		self.start_action()
		CONTEXT = c.PA_CONTEXT_SUCCESS_CB_T(self.context_success)
		self.operation = c.pa_context_suspend_source_by_index(self.context,
			index, suspend,
			CONTEXT, None)
		self.pulse_iterate()

	def pulse_set_source_port(self, index, port):
		self.start_action()
		CONTEXT = c.PA_CONTEXT_SUCCESS_CB_T(self.context_success)
		self.operation = c.pa_context_set_source_port_by_index(self.context,
			index, port,
			CONTEXT, None)
		self.pulse_iterate()

	def pulse_source_output_mute(self, index, mute):
		self.start_action()
		CONTEXT = c.PA_CONTEXT_SUCCESS_CB_T(self.context_success)
		self.operation = c.pa_context_set_source_output_mute(self.context,
			index, mute,
			CONTEXT, None)
		self.pulse_iterate()

	def pulse_source_output_move(self, index, sink_index):
		self.start_action()
		CONTEXT = c.PA_CONTEXT_SUCCESS_CB_T(self.context_success)
		self.operation = c.pa_context_move_source_output_by_index(self.context,
			index, sink_index,
			CONTEXT, None)
		self.pulse_iterate()

	def pulse_source_mute(self, index, mute):
		self.start_action()
		CONTEXT = c.PA_CONTEXT_SUCCESS_CB_T(self.context_success)
		self.operation = c.pa_context_set_source_mute_by_index(self.context,
			index, mute,
			CONTEXT, None)
		self.pulse_iterate()

	def reconnect(self):
		self.context = c.pa_context_new(self.mainloop_api, self.client_name)
		c.pa_context_set_state_callback(self.context, self.pa_state_cb, None)
		self.start_action()
		if c.pa_context_connect(self.context, self.server, 0, None) < 0:
			if self.retry:
				c.pa_context_disconnect(self.context)
				return
			self.pulse_context_error()
		self.pulse_iterate()

	def pulse_run(self):
		self.ret = pointer(c_int(0))
		c.pa_mainloop_run(self.mainloop, self.ret)

	def pulse_iterate(self, times=1):
		self.ret = pointer(c_int())
		c.pa_mainloop_iterate(self.mainloop, times, self.ret)
		while not self.action_done:
			c.pa_mainloop_iterate(self.mainloop, times, self.ret)


class PulseSink(object):

	def __init__(self, index, name, mute, volume, client):
		self.index = index
		self.name = name
		self.mute = mute
		self.volume = volume
		self.client = client


class PulseSinkInfo(PulseSink):

	def __init__(self, pa_sink_info):
		PulseSink.__init__(self, pa_sink_info.index,
			pa_sink_info.name,
			pa_sink_info.mute,
			PulseVolumeC(pa_sink_info.volume),
			PulseClient(self.__class__.__name__))
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
		self.ports = [PulsePort(pa_sink_info.ports[i].contents)
			for i in range(self.n_ports)]
		self.active_port = None
		if self.n_ports:
			self.active_port = PulsePort(pa_sink_info.active_port.contents)

	def __str__(self):
		return 'ID: {}, Name: {}, Mute: {}, {}'.format(
			self.index, self.description, self.mute, self.volume)


class PulseSinkInputInfo(PulseSink):

	def __init__(self, pa_sink_input_info):
		PulseSink.__init__(self, pa_sink_input_info.index,
			pa_sink_input_info.name,
			pa_sink_input_info.mute,
			PulseVolumeC(pa_sink_input_info.volume),
			PulseClient(pa_sink_input_info.name))
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


class PulseSource(object):

	def __init__(self, index, name, mute, volume, client):
		self.index = index
		self.name = name
		self.mute = mute
		self.client = client
		self.volume = volume


class PulseSourceInfo(PulseSource):

	def __init__(self, pa_source_info):
		PulseSource.__init__(self, pa_source_info.index,
			pa_source_info.name,
			pa_source_info.mute,
			PulseVolumeC(pa_source_info.volume),
			PulseClient(self.__class__.__name__))
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
		if self.n_ports:
			self.active_port = PulsePort(pa_source_info.active_port.contents)

	def __str__(self):
		return 'ID: {}, Name: {}, Mute: {}, {}'.format(
			self.index, self.description, self.mute, self.volume)


class PulseSourceOutputInfo(PulseSource):

	def __init__(self, pa_source_output_info):
		PulseSource.__init__(self, pa_source_output_info.index,
			pa_source_output_info.name,
			pa_source_output_info.mute,
			PulseVolumeC(pa_source_output_info.volume),
			PulseClient(pa_source_output_info.name))
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


class PulseVolume(object):

	def __init__(self, values=0, channels=2):
		values = max(min(values, 150), 0)
		self.channels = channels
		self.values = [values] * self.channels

	def to_c(self):
		self.values = list(map(lambda x: max(min(x, 150), 0), self.values))
		cvolume = c.PA_CVOLUME()
		cvolume.channels = self.channels
		for x in range(self.channels):
			cvolume.values[x] = round((self.values[x] * c.PA_VOLUME_NORM) / 100)
		return cvolume

	def __str__(self):
		return 'Channels: {}, Volumes: {}'.format(
			self.channels, [str(x) + '%' for x in self.values])


class PulseVolumeC(PulseVolume):

	def __init__(self, cvolume):
		self.channels = cvolume.channels
		self.values = [(round(x * 100 / c.PA_VOLUME_NORM))
			for x in cvolume.values[:self.channels]]
