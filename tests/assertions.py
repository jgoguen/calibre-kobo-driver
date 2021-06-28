# vim: fileencoding=UTF-8:expandtab:autoindent:ts=4:sw=4:sts=4

import sys
import unittest


# The unittest framework doesn't print tracebacks from any frame with __unittest set to
# True in their globals.
__unittest = True


class TestAssertions(unittest.TestCase):
    """Additional useful unittest assertion functions.

    Note that because this class subclasses unittest.TestCase, any class using this
    must not subclass TestCase directly.
    """

    def __is_any_string_type(self, value):  # type: (...) -> bool
        if isinstance(value, str):
            return True

        if sys.version_info.major < 3:
            # Skip flake8 here, basestring is only defined in Python 2 but linting is
            # done for Python 2 and 3.
            if isinstance(value, basestring):  # noqa: F821
                return True

        return False

    def assertIsNotNoneOrEmptyString(self, value):
        try:
            self.assertIsNoneOrEmptyString(value)
        except AssertionError:
            # But it must still be a string type
            if not self.__is_any_string_type(value):
                self.fail("value must be a string type")
        except Exception:
            raise
        else:
            self.fail("value must not be None and must not be empty string")

    def assertIsNoneOrEmptyString(self, value):
        if value is not None:
            if not self.__is_any_string_type(value):
                # value is not None and is not any string type
                self.fail("value must be None or a string type")

            # value is not None and is a string type
            if value.strip() != "":
                # value is not empty
                self.fail("expected empty string, got: {0}".format(value))
