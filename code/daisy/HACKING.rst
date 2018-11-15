daisycloud-core Style Commandments
=======================

- Step 1: Read the OpenStack Style Commandments
  https://docs.openstack.org/hacking/latest/
- Step 2: Read on

daisycloud-core Specific Commandments
--------------------------

- [G316] Change assertTrue(isinstance(A, B)) by optimal assert like
  assertIsInstance(A, B)
- [G317] Change assertEqual(type(A), B) by optimal assert like
  assertIsInstance(A, B)
- [G318] Change assertEqual(A, None) or assertEqual(None, A) by optimal assert like
  assertIsNone(A)
- [G319] Validate that debug level logs are not translated
- [G320] For python 3 compatibility, use six.text_type() instead of unicode()
- [G321] Validate that LOG messages, except debug ones, have translations
- [G322] Validate that LOG.info messages use _LI.
- [G323] Validate that LOG.exception messages use _LE.
- [G324] Validate that LOG.error messages use _LE.
- [G325] Validate that LOG.critical messages use _LC.
- [G326] Validate that LOG.warning messages use _LW.
- [G327] Prevent use of deprecated contextlib.nested