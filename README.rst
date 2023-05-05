python-pulse-control (pulsectl module)
======================================

Python (3.x and 2.x) blocking high-level interface and ctypes-based bindings
for PulseAudio_ (libpulse), to use in a simple synchronous code.

Wrappers are mostly for mixer-like controls and introspection-related operations,
as opposed to e.g. submitting sound samples to play and player-like client.

For async version to use with asyncio_, see `pulsectl-asyncio`_ project instead.

Originally forked from pulsemixer_ project, which had this code bundled.

.. _PulseAudio: https://wiki.freedesktop.org/www/Software/PulseAudio/
.. _asyncio: https://docs.python.org/3/library/asyncio.html
.. _pulsectl-asyncio: https://pypi.org/project/pulsectl-asyncio/
.. _pulsemixer: https://github.com/GeorgeFilipkin/pulsemixer/

|

.. contents::
  :backlinks: none

Repository URLs:

- https://github.com/mk-fg/python-pulse-control
- https://codeberg.org/mk-fg/python-pulse-control
- https://fraggod.net/code/git/python-pulse-control



Usage
-----

Simple example::

  import pulsectl

  with pulsectl.Pulse('volume-increaser') as pulse:
    for sink in pulse.sink_list():
      # Volume is usually in 0-1.0 range, with >1.0 being soft-boosted
      pulse.volume_change_all_chans(sink, 0.1)

Listening for server state change events::

  import pulsectl

  with pulsectl.Pulse('event-printer') as pulse:
    # print('Event types:', pulsectl.PulseEventTypeEnum)
    # print('Event facilities:', pulsectl.PulseEventFacilityEnum)
    # print('Event masks:', pulsectl.PulseEventMaskEnum)

    def print_events(ev):
      print('Pulse event:', ev)
      ### Raise PulseLoopStop for event_listen() to return before timeout (if any)
      # raise pulsectl.PulseLoopStop

    pulse.event_mask_set('all')
    pulse.event_callback_set(print_events)
    pulse.event_listen(timeout=10)

Misc other tinkering::

  >>> import pulsectl
  >>> pulse = pulsectl.Pulse('my-client-name')

  >>> pulse.sink_list()
  [<PulseSinkInfo at 7f85cfd053d0 - desc='Built-in Audio', index=0L, mute=0, name='alsa-speakers', channels=2, volumes='44.0%, 44.0%'>]

  >>> pulse.sink_input_list()
  [<PulseSinkInputInfo at 7fa06562d3d0 - index=181L, mute=0, name='mpv Media Player', channels=2, volumes='25.0%, 25.0%'>]

  >>> pulse.sink_input_list()[0].proplist
  {'application.icon_name': 'mpv',
   'application.language': 'C',
   'application.name': 'mpv Media Player',
   ...
   'native-protocol.version': '30',
   'window.x11.display': ':1.0'}

  >>> pulse.source_list()
  [<PulseSourceInfo at 7fcb0615d8d0 - desc='Monitor of Built-in Audio', index=0L, mute=0, name='alsa-speakers.monitor', channels=2, volumes='100.0%, 100.0%'>,
   <PulseSourceInfo at 7fcb0615da10 - desc='Built-in Audio', index=1L, mute=0, name='alsa-mic', channels=2, volumes='100.0%, 100.0%'>]

  >>> sink = pulse.sink_list()[0]
  >>> pulse.volume_change_all_chans(sink, -0.1)
  >>> pulse.volume_set_all_chans(sink, 0.5)

  >>> pulse.server_info().default_sink_name
  'alsa_output.pci-0000_00_14.2.analog-stereo'
  >>> pulse.default_set(sink)

  >>> card = pulse.card_list()[0]
  >>> card.profile_list
  [<PulseCardProfileInfo at 7f02e7e88ac8 - description='Analog Stereo Input', n_sinks=0, n_sources=1, name='input:analog-stereo', priority=60>,
   <PulseCardProfileInfo at 7f02e7e88b70 - description='Analog Stereo Output', n_sinks=1, n_sources=0, name='output:analog-stereo', priority=6000>,
   ...
   <PulseCardProfileInfo at 7f02e7e9a4e0 - description='Off', n_sinks=0, n_sources=0, name='off', priority=0>]
  >>> pulse.card_profile_set(card, 'output:hdmi-stereo')

  >>> help(pulse)
  ...

  >>> pulse.close()

Current code logic is that all methods are invoked through the Pulse instance,
and everything returned from these are "Pulse-Something-Info" objects - thin
wrappers around C structs that describe the thing, without any methods attached.

Aside from a few added convenience methods, most of them should have similar
signature and do same thing as their C libpulse API counterparts, so see
`pulseaudio doxygen documentation`_ for more information on them.

Pulse client can be integrated into existing eventloop (e.g. asyncio, twisted,
etc) using ``Pulse.set_poll_func()`` or ``Pulse.event_listen()`` in a separate
thread.

Somewhat extended usage example can be found in `pulseaudio-mixer-cli`_ project
code, as well as tests here.

.. _pulseaudio doxygen documentation: https://freedesktop.org/software/pulseaudio/doxygen/introspect_8h.html
.. _pulseaudio-mixer-cli: https://github.com/mk-fg/pulseaudio-mixer-cli/blob/master/pa-mixer-mk3.py



Notes
-----

Some less obvious things are described in this section.


Things not yet wrapped/exposed in python
````````````````````````````````````````

There are plenty of information, methods and other things in libpulse not yet
wrapped/exposed by this module, as they weren't needed (yet) for author/devs
use-case(s).

Making them accessible from python code can be as simple as adding an attribute
name to the "c_struct_fields" value in PulseSomethingInfo objects.

See `github #3 <https://github.com/mk-fg/python-pulse-control/issues/3>`_
for a more concrete example of finding/adding such stuff.

For info and commands that are not available through libpulse introspection API,
it is possible to use ``pulsectl.connect_to_cli()`` fallback function, which
will open unix socket to server's "module-cli" (signaling to load it, if
necessary), which can be used in exactly same way as "pacmd" tool (not to be
confused with "pactl", which uses native protocol instead of module-cli) or
pulseaudio startup files (e.g. "default.pa").

Probably a bad idea to parse string output from commands there though, as these
are not only subject to change, but can also vary depending on system locale.


Volume
``````

In PulseAudio, "volume" for anything is not a flat number, but essentially a
list of numbers, one per channel (as in "left", "right", "front", "rear", etc),
which should correspond to channel map of the object it relates/is-applied to.

In this module, such lists are represented by PulseVolumeInfo objects.

I.e. ``sink.volume`` is a PulseVolumeInfo instance, and all thin/simple wrappers
that accept index of the object, expect such instance to be passed, e.g.
``pulse.sink_input_volume_set(sink.index, sink.volume)``.

There are convenience ``volume_get_all_chans``, ``volume_set_all_chans`` and
``volume_change_all_chans`` methods to get/set/adjust volume as/by a single
numeric value, which is also accessible on PulseVolumeInfo objects as a
``value_flat`` property.

PulseVolumeInfo can be constructed from a numeric volume value plus number of
channels, or a python list of per-channel numbers.

All per-channel volume values in PulseVolumeInfo (and flat values in the wrapper
funcs above), are float objects in 0-65536 range, with following meanings:

* 0.0 volume is "no sound" (corresponds to PA_VOLUME_MUTED).

* 1.0 value is "current sink volume level", 100% or PA_VOLUME_NORM.

* >1.0 and up to 65536.0 (PA_VOLUME_MAX / PA_VOLUME_NORM) - software-boosted
  sound volume (higher values will negatively affect sound quality).

Probably a good idea to set volume only in 0-1.0 range and boost volume in
hardware without quality loss, e.g. by tweaking sink volume (which corresponds
to ALSA/hardware volume), if that option is available.

Note that ``flat-volumes=yes`` option ("yes" by default on some distros, "no" in
e.g. Arch Linux) in pulseaudio daemon.conf already scales device-volume with the
volume of the "loudest" application, so already does what's suggested above.

Fractional volume values used in the module get translated (in a linear fashion)
to/from pa_volume_t integers for libpulse. See ``src/pulse/volume.h`` in
pulseaudio sources for all the gory details on the latter (e.g. how it relates
to sound level in dB).

Code example::

  from pulsectl import Pulse, PulseVolumeInfo

  with Pulse('volume-example') as pulse:
    sink_input = pulse.sink_input_list()[0] # first random sink-input stream

    volume = sink_input.volume
    print(volume.values) # list of per-channel values (floats)
    print(volume.value_flat) # average level across channels (float)

    time.sleep(1)

    volume.value_flat = 0.3 # sets all volume.values to 0.3
    pulse.volume_set(sink_input, volume) # applies the change

    time.sleep(1)

    n_channels = len(volume.values)
    new_volume = PulseVolumeInfo(0.5, n_channels) # 0.5 across all n_channels
    # new_volume = PulseVolumeInfo([0.15, 0.25]) # from a list of channel levels (stereo)
    pulse.volume_set(sink_input, new_volume)
    # pulse.sink_input_volume_set(sink_input.index, new_volume) # same as above

In most common cases, doing something like
``pulse.volume_set_all_chans(sink_input, 0.2)`` should do the trick though -
no need to bother with specific channels in PulseVolumeInfo there.


String values
`````````````

libpulse explicitly returns utf-8-encoded string values, which are always
decoded to "abstract string" type in both python-2 (where it's called "unicode")
and python-3 ("str"), for consistency.

It might be wise to avoid mixing these with encoded strings ("bytes") in the code,
especially in python-2, where "bytes" is often used as a default string type.


Enumerated/named values (enums)
```````````````````````````````

In place of C integers that correspond to some enum or constant (e.g. -1 for
PA_SINK_INVALID_STATE), module returns EnumValue objects, which are comparable
to strings ("str" type in py2/py3).

For example::

  >>> pulsectl.PulseEventTypeEnum.change == 'change'
  True
  >>> pulsectl.PulseEventTypeEnum.change
  <EnumValue event-type=change>
  >>> pulsectl.PulseEventTypeEnum
  <Enum event-type [change new remove]>

It might be preferrable to use enums instead of strings in the code so that
interpreter can signal error on any typos or unknown values specified, as
opposed to always silently failing checks with bogus strings.


Event-handling code, threads
````````````````````````````

libpulse clients always work as an event loop, though this module kinda hides
it, presenting a more old-style blocking interface.

So what happens on any call (e.g. ``pulse.mute(...)``) is:

* Make a call to libpulse, specifying callback for when operation will be completed.
* Run libpulse event loop until that callback gets called.
* Return result passed to that callback call, if any (for various "get" methods).

``event_callback_set()`` and ``event_listen()`` calls essentally do raw first
and second step here.

Which means that any pulse calls from callback function can't be used when
``event_listen()`` (or any other pulse call through this module, for that matter)
waits for return value and runs libpulse loop already.

One can raise PulseLoopStop exception there to make ``event_listen()`` return,
run whatever pulse calls after that, then re-start the ``event_listen()`` thing.

This will not miss any events, as all blocking calls do same thing as
``event_listen()`` does (second step above), and can cause callable passed to
``event_callback_set()`` to be called (when loop is running).

Also, same instance of libpulse eventloop can't be run from different threads,
naturally, so if threads are used, client can be initialized with
``threading_lock=True`` option (can also accept lock instance instead of True)
to create a mutex around step-2 (run event loop) from the list above, so
multiple threads won't do it at the same time.

For proper python eventloop integration (think twisted or asyncio),
use `pulsectl-asyncio`_ module instead.

There are also some tricks mentioned in `github #11
<https://github.com/mk-fg/python-pulse-control/issues/11>`_ to shoehorn this
module into async apps, but even with non-asyncio eventloop, starting from
pulsectl-asyncio would probably be much easier.


Tests
`````

Test code is packaged/installed with the module and can be useful to run when
changing module code, or to check if current python, module and pulseudio
versions all work fine together.

Commands to run tests from either checkout directory or installed module::

  % python2 -m unittest discover
  % python3 -m unittest discover

Note that if "pulsectl" module is available both in current directory
(e.g. checkout dir) and user/system python module path, former should always
take priority for commands above.

Add e.g. ``-k test_stream_move`` for commands above to match and run specific
test(s), and when isolating specific failure, it might also be useful to run
with PA_DEBUG=1 env-var to get full verbose pulseaudio log, for example::

  % PA_DEBUG=1 python -m unittest discover -k test_module_funcs

Test suite runs ad-hoc isolated pulseaudio instance with null-sinks (not
touching hardware), custom (non-default) startup script and environment,
and interacts only with that instance, terminating it afterwards.
Still uses system/user daemon.conf files though, so these can affect the tests.

Any test failures can indicate incompatibilities, bugs in the module code,
issues with pulseaudio (or its daemon.conf) and underlying dependencies.
There are no "expected" test case failures.

All tests can run for up to 10 seconds currently (v19.9.6), due to some
involving playback (using paplay from /dev/urandom) being time-sensitive.


Changelog and versioning scheme
```````````````````````````````

This package uses one-version-per-commit scheme (updated by pre-commit hook)
and pretty much one release per git commit, unless more immediate follow-up
commits are planned or too lazy to run ``py setup.py sdist bdist_wheel upload``
for some trivial README typo fix.

| Version scheme: ``{year}.{month}.{git-commit-count-this-month}``
| I.e. "16.9.10" is "11th commit on Sep 2016".
|

There is a `CHANGES.rst <CHANGES.rst>`_ file with the list of any intentional
breaking changes (should be exceptionally rare, if any) and new/added
non-trivial functionality.

| It can be a bit out of date though, as one has to remember to update it manually.
| "Last synced/updated:" line there might give a hint as to by how much.



Installation
------------

It's a regular package for Python (3.x or 2.x).

`If a package is available for your distribution`_,
using your package manager is the recommended way to install it.

Otherwise, using pip_ is the best way::

  % pip install pulsectl

(add --user option to install into $HOME for current user only)

Be sure to use python3/python2, pip3/pip2, easy_install-... commands
based on which python version you want to install the module for,
if you are still using python2 (and likely have python3 on the system as well).

If you don't have "pip" command::

  % python -m ensurepip
  % python -m pip install --upgrade pip
  % python -m pip install pulsectl

(same suggestion wrt "install --user" as above)

On a very old systems, one of these might work::

  % curl https://bootstrap.pypa.io/get-pip.py | python
  % pip install pulsectl

  % easy_install pulsectl

  % git clone --depth=1 https://github.com/mk-fg/python-pulse-control
  % cd python-pulse-control
  % python setup.py install

(all of install-commands here also have --user option)

Current-git version can be installed like this::

  % pip install 'git+https://github.com/mk-fg/python-pulse-control#egg=pulsectl'

Note that to install stuff to system-wide PATH and site-packages
(without --user), elevated privileges (i.e. root and su/sudo) are often required.

Use "...install --user", `~/.pydistutils.cfg`_ or virtualenv_
to do unprivileged installs into custom paths.

More info on python packaging can be found at `packaging.python.org`_.

.. _If a package is available for your distribution: https://repology.org/project/python:pulsectl/versions
.. _pip: http://pip-installer.org/
.. _~/.pydistutils.cfg: http://docs.python.org/install/index.html#distutils-configuration-files
.. _virtualenv: http://pypi.python.org/pypi/virtualenv
.. _packaging.python.org: https://packaging.python.org/installing/



Links
-----

* pulsemixer_ - initial source for this project (embedded in the tool).

* `pulsectl-asyncio`_ - similar libpulse wrapper to this one, but for async python code.

* `libpulseaudio <https://github.com/thelinuxdude/python-pulseaudio/>`_ -
  different libpulse bindings module, more low-level, auto-generated from
  pulseaudio header files.

  Branches there have bindings for different (newer) pulseaudio versions.

* `pypulseaudio <https://github.com/liamw9534/pypulseaudio/>`_ -
  high-level bindings module, rather similar to this one.

* `pulseaudio-mixer-cli`_ - alsamixer-like script built on top of this module.
