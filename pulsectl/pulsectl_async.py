import asyncio
import inspect
import sys
import itertools as it
import functools as ft
import traceback
from contextlib import contextmanager, asynccontextmanager
from typing import Optional, AsyncIterator, Coroutine

from .pa_asyncio_mainloop import PythonMainLoop
from .pulsectl import (
	PulseError, PulseEventTypeEnum, PulseEventFacilityEnum, PulseEventInfo,
	PulseEventMaskEnum, PulseLoopStop, PulseOperationFailed, PulseIndexError, PulseSinkInfo, PulseSourceInfo,
	PulseCardInfo, PulseSinkInputInfo, PulseSourceOutputInfo, PulseClientInfo, PulseServerInfo, PulseModuleInfo,
	is_list, PulseOperationInvalid, PulsePortInfo, PulseExtStreamRestoreInfo, PulseUpdateEnum, is_str,
	assert_pulse_object, PulseDisconnected, unicode)
from . import _pulsectl as c


# TODO alternative for event_callback_set (e.g. async generator)

class PulseAsync(object):

	_ctx = None

	def __init__(self, client_name=None, server=None, loop: Optional[asyncio.AbstractEventLoop] = None):
		'''Connects to specified pulse server by default.
			Specifying "connect=False" here prevents that, but be sure to call connect() later.
			"connect=False" can also be used here to
				have control over options passed to connect() method.'''
		self.name = client_name or 'pulsectl'
		self.server = server
		self.connected = asyncio.Event(loop=loop)
		self.disconnected = asyncio.Event(loop=loop)
		self.disconnected.set()
		self._ctx = self._loop = None
		self._actions, self._action_ids = dict(),\
			it.chain.from_iterable(map(range, it.repeat(2**30)))
		self.init(loop)

	def init(self, loop: Optional[asyncio.AbstractEventLoop]):
		self._pa_state_cb = c.PA_STATE_CB_T(self._pulse_state_cb)
		self._pa_subscribe_cb = c.PA_SUBSCRIBE_CB_T(self._pulse_subscribe_cb)

		self._loop = PythonMainLoop(loop or asyncio.get_event_loop())

		self._ctx_init()
		self.event_types = sorted(PulseEventTypeEnum._values.values())
		self.event_facilities = sorted(PulseEventFacilityEnum._values.values())
		self.event_masks = sorted(PulseEventMaskEnum._values.values())
		self.event_callback = None

	def _ctx_init(self):
		if self._ctx:
			self.disconnect()
			c.pa.context_unref(self._ctx)
		self._ctx = c.pa.context_new(self._loop.api_pointer, self.name)
		self.connected.clear()
		self.disconnected.clear()
		c.pa.context_set_state_callback(self._ctx, self._pa_state_cb, None)
		c.pa.context_set_subscribe_callback(self._ctx, self._pa_subscribe_cb, None)

	async def connect(self, autospawn=False):
		'''Connect to pulseaudio server.
			"autospawn" option will start new pulse daemon, if necessary.'''
		if self.connected.is_set():
			self._ctx_init()
		flags = 0
		if not autospawn:
			flags |= c.PA_CONTEXT_NOAUTOSPAWN
		try:
			c.pa.context_connect(self._ctx, self.server, flags, None)
			await self._wait_disconnect_or(self.connected.wait())
		except (c.pa.CallError, PulseDisconnected) as e:
			raise PulseError('Failed to connect to pulseaudio server') from e

	def disconnect(self):
		if not self._ctx or not self.connected.is_set():
			return
		c.pa.context_disconnect(self._ctx)

	def close(self):
		if not self._loop: return
		try:
			self.disconnect()
			c.pa.context_unref(self._ctx)
			self._loop.stop(0)
		finally: self._ctx = self._loop = None

	def __enter__(self): return self
	def __exit__(self, err_t, err, err_tb): self.close()

	async def _wait_disconnect_or(self, coroutine: Coroutine):
		wait_disconnected = asyncio.create_task(self.disconnected.wait())
		other_task = asyncio.create_task(coroutine)
		done, pending = await asyncio.wait((wait_disconnected, other_task), return_when=asyncio.FIRST_COMPLETED)
		for task in pending:
			task.cancel()
		if other_task in pending:
			raise PulseDisconnected()
		else:
			return other_task.result()

	def _pulse_state_cb(self, ctx, _userdata):
		state = c.pa.context_get_state(ctx)
		if state >= c.PA_CONTEXT_READY:
			if state == c.PA_CONTEXT_READY:
				self.connected.set()
				self.disconnected.clear()
			elif state in [c.PA_CONTEXT_FAILED, c.PA_CONTEXT_TERMINATED]:
				self.connected.clear()
				self.disconnected.set()
				for future in self._actions:
					future.set_exception(PulseDisconnected())

	def _pulse_subscribe_cb(self, ctx, ev, idx, userdata):
		if not self.event_callback: return
		n = ev & c.PA_SUBSCRIPTION_EVENT_FACILITY_MASK
		ev_fac = PulseEventFacilityEnum._c_val(n, 'ev.facility.{}'.format(n))
		n = ev & c.PA_SUBSCRIPTION_EVENT_TYPE_MASK
		ev_t = PulseEventTypeEnum._c_val(n, 'ev.type.{}'.format(n))
		try: self.event_callback(PulseEventInfo(ev_t, ev_fac, idx))
		except PulseLoopStop: self._loop_stop = True

	@asynccontextmanager
	async def _pulse_op_cb(self, raw=False):
		act_id = next(self._action_ids)
		self._actions[act_id] = self._loop.loop.create_future()
		try:
			def cb (s=True,k=act_id):
				if s: self._loop.loop.call_soon_threadsafe(self._actions[k].set_result, None)
				else: self._loop.loop.call_soon_threadsafe(self._actions[k].set_exception, PulseOperationFailed(act_id))
			if not raw: cb = c.PA_CONTEXT_SUCCESS_CB_T(lambda ctx,s,d,cb=cb: cb(s))
			yield cb
			await self._actions[act_id]
		finally: self._actions.pop(act_id, None)


	def _pulse_info_cb(self, info_cls, data_list, done_cb, ctx, info, eof, userdata):
		# No idea where callbacks with "userdata != NULL" come from,
		#  but "info" pointer in them is always invalid, so they are discarded here.
		# Looks like some kind of mixup or corruption in libpulse memory?
		# See also: https://github.com/mk-fg/python-pulse-control/issues/35
		if userdata is not None: return
		# Empty result list and conn issues are checked elsewhere.
		# Errors here are non-descriptive (errno), so should not be useful anyway.
		# if eof < 0: done_cb(s=False)
		if eof: done_cb()
		else: data_list.append(info_cls(info[0]))

	def _pulse_get_list(cb_t, pulse_func, info_cls, singleton=False, index_arg=True):
		async def _wrapper_method(self, index=None):
			data = list()
			async with self._pulse_op_cb(raw=True) as cb:
				cb = cb_t(
					ft.partial(self._pulse_info_cb, info_cls, data, cb) if not singleton else
					lambda ctx, info, userdata, cb=cb: data.append(info_cls(info[0])) or cb() )
				pa_op = pulse_func( self._ctx,
					*([index, cb, None] if index is not None else [cb, None]) )
			c.pa.operation_unref(pa_op)
			data = data or list()
			if index is not None or singleton:
				if not data: raise PulseIndexError(index)
				data, = data
			return data
		_wrapper_method.__name__ = '...'
		_wrapper_method.__doc__ = 'Signature: func({})'.format(
			'' if pulse_func.__name__.endswith('_list') or singleton or not index_arg else 'index' )
		return _wrapper_method

	get_sink_by_name = _pulse_get_list(
		c.PA_SINK_INFO_CB_T,
		c.pa.context_get_sink_info_by_name, PulseSinkInfo )
	get_source_by_name = _pulse_get_list(
		c.PA_SOURCE_INFO_CB_T,
		c.pa.context_get_source_info_by_name, PulseSourceInfo )
	get_card_by_name = _pulse_get_list(
		c.PA_CARD_INFO_CB_T,
		c.pa.context_get_card_info_by_name, PulseCardInfo )

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
	server_info = _pulse_get_list(
		c.PA_SERVER_INFO_CB_T, c.pa.context_get_server_info, PulseServerInfo, singleton=True )
	module_info = _pulse_get_list(
		c.PA_MODULE_INFO_CB_T, c.pa.context_get_module_info, PulseModuleInfo )
	module_list = _pulse_get_list(
		c.PA_MODULE_INFO_CB_T, c.pa.context_get_module_info_list, PulseModuleInfo )

	def _pulse_method_call(pulse_op, func=None, index_arg=True):
		'''Creates following synchronous wrapper for async pa_operation callable:
			wrapper(index, ...) -> pulse_op(index, [*]args_func(...))
			index_arg=False: wrapper(...) -> pulse_op([*]args_func(...))'''
		async def _wrapper(self, *args, **kws):
			if index_arg:
				if 'index' in kws: index = kws.pop('index')
				else: index, args = args[0], args[1:]
			pulse_args = func(*args, **kws) if func else list()
			if not is_list(pulse_args): pulse_args = [pulse_args]
			if index_arg: pulse_args = [index] + list(pulse_args)
			async with self._pulse_op_cb() as cb:
				try: pulse_op(self._ctx, *(list(pulse_args) + [cb, None]))
				except c.ArgumentError as err: raise TypeError(err.args)
				except c.pa.CallError as err: raise PulseOperationInvalid(err.args[-1])
		func_args = list(inspect.getargspec(func or (lambda: None)))
		func_args[0] = list(func_args[0])
		if index_arg: func_args[0] = ['index'] + func_args[0]
		_wrapper.__name__ = '...'
		_wrapper.__doc__ = 'Signature: func' + inspect.formatargspec(*func_args)
		if func.__doc__: _wrapper.__doc__ += '\n\n' + func.__doc__
		return _wrapper

	card_profile_set_by_index = _pulse_method_call(
		c.pa.context_set_card_profile_by_index, lambda profile_name: profile_name )

	sink_default_set = _pulse_method_call(
		c.pa.context_set_default_sink, index_arg=False,
		func=lambda sink: sink.name if isinstance(sink, PulseSinkInfo) else sink )
	source_default_set = _pulse_method_call(
		c.pa.context_set_default_source, index_arg=False,
		func=lambda source: source.name if isinstance(source, PulseSourceInfo) else source )

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


	async def module_load(self, name, args=''):
		if is_list(args): args = ' '.join(args)
		name, args = map(c.force_bytes, [name, args])
		data = list()
		async with self._pulse_op_cb(raw=True) as cb:
			cb = c.PA_CONTEXT_INDEX_CB_T(
				lambda ctx, index, userdata, cb=cb: data.append(index) or cb() )
			try: c.pa.context_load_module(self._ctx, name, args, cb, None)
			except c.pa.CallError as err: raise PulseOperationInvalid(err.args[-1])
		index, = data
		return index

	module_unload = _pulse_method_call(c.pa.context_unload_module, None)


	async def stream_restore_test(self):
		'Returns module-stream-restore version int (e.g. 1) or None if it is unavailable.'
		data = list()
		async with self._pulse_op_cb(raw=True) as cb:
			cb = c.PA_EXT_STREAM_RESTORE_TEST_CB_T(
				lambda ctx, version, userdata, cb=cb: data.append(version) or cb() )
			try: c.pa.ext_stream_restore_test(self._ctx, cb, None)
			except c.pa.CallError as err: raise PulseOperationInvalid(err.args[-1])
		version, = data
		return version if version != c.PA_INVALID else None

	stream_restore_read = _pulse_get_list(
		c.PA_EXT_STREAM_RESTORE_READ_CB_T,
		c.pa.ext_stream_restore_read, PulseExtStreamRestoreInfo, index_arg=False )
	stream_restore_list = stream_restore_read # for consistency with other *_list methods

	@ft.partial(_pulse_method_call, c.pa.ext_stream_restore_write, index_arg=False)
	def stream_restore_write( obj_name_or_list,
			mode='merge', apply_immediately=False, **obj_kws ):
		'''Update module-stream-restore db entry for specified name.
			Can be passed PulseExtStreamRestoreInfo object or list of them as argument,
				or name string there and object init keywords (e.g. volume, mute, channel_list, etc).
			"mode" is PulseUpdateEnum value of
				'merge' (default), 'replace' or 'set' (replaces ALL entries!!!).'''
		mode = PulseUpdateEnum[mode]._c_val
		if is_str(obj_name_or_list):
			obj_name_or_list = PulseExtStreamRestoreInfo(obj_name_or_list, **obj_kws)
		if isinstance(obj_name_or_list, PulseExtStreamRestoreInfo):
			obj_name_or_list = [obj_name_or_list]
		# obj_array is an array of structs, laid out contiguously in memory, not pointers
		obj_array = (c.PA_EXT_STREAM_RESTORE_INFO * len(obj_name_or_list))()
		for n, obj in enumerate(obj_name_or_list):
			obj_struct, dst_struct = obj.to_struct(), obj_array[n]
			for k,t in obj_struct._fields_: setattr(dst_struct, k, getattr(obj_struct, k))
		return mode, obj_array, len(obj_array), int(bool(apply_immediately))

	@ft.partial(_pulse_method_call, c.pa.ext_stream_restore_delete, index_arg=False)
	def stream_restore_delete(obj_name_or_list):
		'''Can be passed string name,
			PulseExtStreamRestoreInfo object or a list of any of these.'''
		if is_str(obj_name_or_list, PulseExtStreamRestoreInfo):
			obj_name_or_list = [obj_name_or_list]
		name_list = list((obj.name if isinstance( obj,
			PulseExtStreamRestoreInfo ) else obj) for obj in obj_name_or_list)
		name_struct = (c.c_char_p * len(name_list))()
		name_struct[:] = list(map(c.force_bytes, name_list))
		return [name_struct]


	async def default_set(self, obj):
		'Set passed sink or source to be used as default one by pulseaudio server.'
		assert_pulse_object(obj)
		method = {
			PulseSinkInfo: self.sink_default_set,
			PulseSourceInfo: self.source_default_set }.get(type(obj))
		if not method: raise NotImplementedError(type(obj))
		await method(obj)

	async def mute(self, obj, mute=True):
		assert_pulse_object(obj)
		method = {
			PulseSinkInfo: self.sink_mute,
			PulseSinkInputInfo: self.sink_input_mute,
			PulseSourceInfo: self.source_mute,
			PulseSourceOutputInfo: self.source_output_mute }.get(type(obj))
		if not method: raise NotImplementedError(type(obj))
		await method(obj.index, mute)
		obj.mute = mute

	async def port_set(self, obj, port):
		assert_pulse_object(obj)
		method = {
			PulseSinkInfo: self.sink_port_set,
			PulseSourceInfo: self.source_port_set }.get(type(obj))
		if not method: raise NotImplementedError(type(obj))
		await method(obj.index, port)
		obj.port_active = port

	async def card_profile_set(self, card, profile):
		assert_pulse_object(card)
		if is_str(profile):
			profile_dict = dict((p.name, p) for p in card.profile_list)
			if profile not in profile_dict:
				raise PulseIndexError( 'Card does not have'
					' profile with specified name: {!r}'.format(profile) )
			profile = profile_dict[profile]
		await self.card_profile_set_by_index(card.index, profile.name)
		card.profile_active = profile

	async def volume_set(self, obj, vol):
		assert_pulse_object(obj)
		method = {
			PulseSinkInfo: self.sink_volume_set,
			PulseSinkInputInfo: self.sink_input_volume_set,
			PulseSourceInfo: self.source_volume_set,
			PulseSourceOutputInfo: self.source_output_volume_set }.get(type(obj))
		if not method: raise NotImplementedError(type(obj))
		await method(obj.index, vol)
		obj.volume = vol

	async def volume_set_all_chans(self, obj, vol):
		assert_pulse_object(obj)
		obj.volume.value_flat = vol
		await self.volume_set(obj, obj.volume)

	async def volume_change_all_chans(self, obj, inc):
		assert_pulse_object(obj)
		obj.volume.values = [max(0, v + inc) for v in obj.volume.values]
		await self.volume_set(obj, obj.volume)

	async def volume_get_all_chans(self, obj):
		# Purpose of this func can be a bit confusing, being here next to set/change ones
		'''Get "flat" volume float value for info-object as a mean of all channel values.
			Note that this DOES NOT query any kind of updated values from libpulse,
				and simply returns value(s) stored in passed object, i.e. same ones for same object.'''
		assert_pulse_object(obj)
		return obj.volume.value_flat

	async def _event_mask_set(self, *masks):
		mask = 0
		for m in masks: mask |= PulseEventMaskEnum[m]._c_val
		async with self._pulse_op_cb() as cb:
			c.pa.context_subscribe(self._ctx, mask, cb, None)

	async def subscribe_events(self, *masks) -> AsyncIterator[PulseEventInfo]:
		if self.event_callback is not None:
			raise RuntimeError('Only a single subscribe_events generator can be used at a time.')
		queue = asyncio.queues.Queue()
		self.event_callback = queue.put_nowait
		try:
			await self._event_mask_set(*masks)
			while True:
				yield await self._wait_disconnect_or(queue.get())
		finally:
			self.event_callback = None
			if self.connected:
				await self._event_mask_set('null')

	async def get_peak_sample(self, source, timeout, stream_idx=None):
		'''Returns peak (max) value in 0-1.0 range for samples in source/stream within timespan.
			"source" can be either int index of pulseaudio source
				(i.e. source.index), its name (source.name), or None to use default source.
			Resulting value is what pulseaudio returns as
				PA_SAMPLE_FLOAT32BE float after "timeout" seconds.
			If specified source does not exist, 0 should be returned after timeout.
			This can be used to detect if there's any sound
				on the microphone or any sound played through a sink via its monitor_source index,
				or same for any specific stream connected to these (if "stream_idx" is passed).
			Sample stream masquerades as
				application.id=org.PulseAudio.pavucontrol to avoid being listed in various mixer apps.
			Example - get peak for specific sink input "si" for 0.8 seconds:
				pulse.get_peak_sample(pulse.sink_info(si.sink).monitor_source, 0.8, si.index)'''
		samples, proplist = [0], c.pa.proplist_from_string('application.id=org.PulseAudio.pavucontrol')
		ss = c.PA_SAMPLE_SPEC(format=c.PA_SAMPLE_FLOAT32BE, rate=25, channels=1)
		s = c.pa.stream_new_with_proplist(self._ctx, 'peak detect', c.byref(ss), None, proplist)
		c.pa.proplist_free(proplist)

		@c.PA_STREAM_REQUEST_CB_T
		def read_cb(s, bs, userdata):
			buff, bs = c.c_void_p(), c.c_int(bs)
			c.pa.stream_peek(s, buff, c.byref(bs))
			try:
				if not buff or bs.value < 4: return
				# This assumes that native byte order for floats is BE, same as pavucontrol
				samples[0] = max(samples[0], c.cast(buff, c.POINTER(c.c_float))[0])
			finally:
				# stream_drop() flushes buffered data (incl. buff=NULL "hole" data)
				# stream.h: "should not be called if the buffer is empty"
				if bs.value: c.pa.stream_drop(s)

		if stream_idx is not None: c.pa.stream_set_monitor_stream(s, stream_idx)
		c.pa.stream_set_read_callback(s, read_cb, None)
		if source is not None: source = unicode(source).encode('utf-8')
		try:
			c.pa.stream_connect_record( s, source,
				c.PA_BUFFER_ATTR(fragsize=4, maxlength=2**32-1),
				c.PA_STREAM_DONT_MOVE | c.PA_STREAM_PEAK_DETECT |
					c.PA_STREAM_ADJUST_LATENCY | c.PA_STREAM_DONT_INHIBIT_AUTO_SUSPEND )
		except c.pa.CallError:
			c.pa.stream_unref(s)
			raise

		await asyncio.sleep(timeout)

		try: c.pa.stream_disconnect(s)
		except c.pa.CallError: pass # stream was removed

		return min(1.0, samples[0])

	async def play_sample(self, name, sink=None, volume=1.0, proplist_str=None):
		'''Play specified sound sample,
				with an optional sink object/name/index, volume and proplist string parameters.
			Sample must be stored on the server in advance, see e.g. "pacmd list-samples".
			See also libcanberra for an easy XDG theme sample loading, storage and playback API.'''
		if isinstance(sink, PulseSinkInfo): sink = sink.index
		sink = str(sink) if sink is not None else None
		proplist = c.pa.proplist_from_string(proplist_str) if proplist_str else None
		volume = int(round(volume*c.PA_VOLUME_NORM))
		async with self._pulse_op_cb() as cb:
			try:
				if not proplist:
					c.pa.context_play_sample(self._ctx, name, sink, volume, cb, None)
				else:
					c.pa.context_play_sample_with_proplist(
						self._ctx, name, sink, volume, proplist, cb, None )
			except c.pa.CallError as err: raise PulseOperationInvalid(err.args[-1])