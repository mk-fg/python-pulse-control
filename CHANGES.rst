=========
 CHANGES
=========

Only (unlikely) intentional breaking changes and new/added non-trivial
functionality is listed here, no bugfixes or commit messages.

Each entry is a package version which change first appears in, followed by
description of the change itself.

Last synced/updated: 17.1.3

---------------------------------------------------------------------------

- 17.6.0: Add PulseCardInfo.port_list.

  These ports are different from sink/source ports in that they have proplist,
  card profiles and some other parameters associated with them, implemented as
  PulseCardPortInfo instances.

- 17.1.3: Add wrappers for card profiles.

  More specifically - PulseCardProfileInfo objects and PulseCardInfo
  "profile_list" and "profile_active" attributes.

  ``pulse.card_profile_set(card, profile)`` can be used to set active profile
  (either by name or PulseCardProfileInfo object).

- 16.11.0: This changelog file was started, thanks to the idea from #12.
