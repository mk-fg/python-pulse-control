python-pulse-control (pulsectl module)
======================================

Python (3.x and 2.x) high-level interface and ctypes-based bindings for
PulseAudio_ (libpulse), mostly focused on mixer-like controls and
introspection-related operations (as opposed to e.g. submitting sound samples to
play, player-like client).

Originally forked from pulsemixer_ project, which had this code bundled.

.. _PulseAudio: https://wiki.freedesktop.org/www/Software/PulseAudio/
.. _pulsemixer: https://github.com/GeorgeFilipkin/pulsemixer/

|

.. contents::
  :backlinks: none



Usage
-----

Simple example::

  from pulsectl import Pulse

  with Pulse('volume-increaser') as pulse:
    for sink in pulse.sink_list():
      # Volume is usually in 0-1.0 range, with >1.0 being soft-boosted
      pulse.volume_change_all_chans(sink, 0.1)

Listening for server state change events::

  from pulsectl import Pulse, PulseLoopStop

  with Pulse('event-printer') as pulse:
    # print('Event types:', ', '.join(pulse.event_types))
    # print('Event facilities:', ', '.join(pulse.event_facilities))
    # print('Event masks:', ', '.join(pulse.event_masks))

    def print_events(ev):
      print('Pulse event:', ev)
      ### Raise PulseLoopStop for event_listen() to return before timeout (if any)
      # raise PulseLoopStop

    pulse.event_mask_set('all')
    pulse.event_callback_set(print_events)
    pulse.event_listen(timeout=10)

Misc other tinkering::

  >>> from pulsectl import Pulse
  >>> pulse = Pulse('my-client-name')

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

  >>> help(pulse)
  ...

Current code logic is that all methods are invoked through the Pulse instance,
and everything returned from these are "Pulse-Something-Info" objects - thin
wrappers around C structs that describe the thing, without any methods attached.

Pulse client can be integrated into existing eventloop (e.g. asyncio, twisted,
etc) using ``Pulse.set_poll_func()`` or ``Pulse.event_listen()`` in a separate
thread.

Somewhat extended usage example can be found in `pulseaudio-mixer-cli`_ project
code.

.. _pulseaudio-mixer-cli: https://github.com/mk-fg/pulseaudio-mixer-cli/blob/master/pa-mixer-mk3.py



Installation
------------

It's a regular package for Python (3.x or 2.x).

Be sure to use python3/python2, pip3/pip2, easy_install-... binaries below,
based on which python version you want to install the module for, if you have
several on the system (as is norm these days for py2-py3 transition).

Using pip_ is the best way::

  % pip install pulsectl

If you don't have pip::

  % easy_install pip
  % pip install pulsectl

Alternatively (see also `pip2014.com`_ and `pip install guide`_)::

  % curl https://raw.github.com/pypa/pip/master/contrib/get-pip.py | python
  % pip install pulsectl

Or, if you absolutely must::

  % easy_install pulsectl

But, you really shouldn't do that.

Current-git version can be installed like this::

  % pip install 'git+https://github.com/mk-fg/python-pulse-control.git#egg=pulsectl'

Note that to install stuff in system-wide PATH and site-packages, elevated
privileges are often required.
Use "...install --user", `~/.pydistutils.cfg`_ or virtualenv_ to do unprivileged
installs into custom paths.

.. _pip: http://pip-installer.org/
.. _pip2014.com: http://pip2014.com/
.. _pip install guide: http://www.pip-installer.org/en/latest/installing.html
.. _~/.pydistutils.cfg: http://docs.python.org/install/index.html#distutils-configuration-files
.. _virtualenv: http://pypi.python.org/pypi/virtualenv



Links
-----

* pulsemixer_ - initial source for this project (embedded in the tool).

* `libpulseaudio <https://github.com/thelinuxdude/python-pulseaudio/>`_ -
  different libpulse bindings module, more low-level, auto-generated from
  pulseaudio header files.

  Branches there have bindings for different (newer) pulseaudio versions.

* `pulseaudio-mixer-cli`_ - alsamixer-like script built on top of this module.
