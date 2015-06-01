"""This module defines I/O ports that serve as interfaces between tasks."""

from __future__ import absolute_import
import json

from romanesco import io, convert, isvalid
from gaia.core.base import GaiaObject


class ValidationError(Exception):

    """An exception type raised when encountering invalid data types."""

    message_format = (
        'Input "{name}" (Python type "{python_type}") is not of the '
        'expected type ("{type}") and format ("{format}")'
    )

    def __init__(self, port, data_spec):
        """Generate a data validation exception.

        :param port: The port that encountered the error
        :type port: :py:class:Port
        :param dict data_spec: The data specification passed to the port.
        """
        self.port = port
        self.data_spec = data_spec

    def __str__(self):
        """Initialize an error message for the exception."""
        return self.message_format.format(
            name=str(self.port.name),
            python_type=str(type(self.data_spec.get('data'))),
            type=str(self.port.type),
            format=str(self.port.format)
        )


class Port(GaiaObject):

    """A port defines a communication channel between tasks.

    Ports enable bidirectional communication between tasks and are responsible
    for ensuring that the connections are compatible.  The primary purpose of
    ports is to specify what types of data tasks can read and write.  This
    information is used by tasks to determine if they can be connected.  Ports
    also provide documentation for the task by describing its inputs and outputs.
    Ports also handle fetching data from and pushing data to remote data stores.

    >>> spec = {'name': 'a', 'type': 'number', 'format': 'number'}
    >>> port = Port(spec)

    The port object is serialized as a json object
    >>> json.loads(str(port)) == spec
    True

    It has several properties derived from the spec
    >>> port.spec == spec
    True
    >>> port.name == spec['name']
    True
    >>> port.type == spec['type']
    True
    >>> port.format == spec['format']
    True

    It also supports auto converting formats and validation by default
    >>> port.auto_convert
    True
    >>> port.auto_validate
    True
    """

    def __init__(self, spec):
        """Initialize the port on a given task.

        :param dict spec: The port data specification
        """
        self._spec = spec.copy()

    @property
    def spec(self):
        """Get the port specification."""
        return self._spec.copy()

    @property
    def name(self):
        """Get the port's name."""
        if 'id' in self.spec:
            return self.spec['id']
        return self.spec.get('name')

    @property
    def type(self):
        """Return the data type."""
        return self.spec.get('type')

    @property
    def format(self):
        """Get the data storage format."""
        return self.spec.get('format')

    @property
    def auto_convert(self):
        """Return whether the port automatically converts between formats."""
        return self.spec.get('auto_convert', True)

    @property
    def auto_validate(self):
        """Return whether the port validates data when fetching and pushing."""
        return self.spec.get('auto_validate', True)

    def validate(self, data_spec):
        """Ensure the given data spec is compatible with this port.

        :param dict data_spec: Data specification
        :returns: bool

        >>> spec = {'name': 'a', 'type': 'number', 'format': 'number'}
        >>> port = Port(spec)

        >>> port.validate({'format': 'number', 'data': 1.5})
        True
        >>> port.validate({'format': 'json', 'data': '1.5'})
        True
        >>> port.validate({'format': 'number', 'data': '1.5'})
        False
        >>> port.validate({'format': 'unknown format', 'data': '...'})
        False
        """
        try:
            return isvalid(self.type, data_spec)
        except Exception:  # catchall validation error
            return False

    def convert(self, data_spec, format):
        """Convert to a  compatible data format.

        :param dict data_spec: Data specification
        :param str format: The target data format
        :returns: dict

        >>> spec = {'name': 'a', 'type': 'number', 'format': 'number'}
        >>> port = Port(spec)

        >>> new_spec = port.convert({'format': 'number', 'data': 1}, 'json')
        >>> new_spec['format']
        'json'
        >>> port.fetch(new_spec)
        1
        """
        return convert(self.type, data_spec, {'format': format})

    def __str__(self):
        """Serialize the port specification."""
        return json.dumps(self.spec)

    def fetch(self, data_spec):
        """Return the data described by the given specification.

        :param dict data_spec: A data specification object
        :returns: data
        :raises ValidationError: when the validation check fails

        >>> port = Port({'name': 'a', 'type': 'number', 'format': 'number'})
        >>> port.fetch({'format': 'number', 'data': -1})
        -1
        """
        if self.auto_validate and not self.validate(data_spec):
            raise ValidationError(self, data_spec)

        if self.auto_convert:
            _data = self.convert(data_spec, self.format)
            data = _data.get('data')
        elif self.format is None or self.format == data_spec.get('format'):
            if 'data' in self.spec and self.spec['data'] is not None:
                data = self.spec['data']
            else:
                data = io.fetch(data_spec, task_input=self.spec).get('data')
        else:
            raise Exception('Expected matching data formats ({} != {})' % (
                str(data_spec['format']), str(self.format)
            ))

        return data

    def push(self, data_spec):
        """Write data a to remote destination according the to specification.

        :param dict data_spec: A data specification object
        :returns: dict

        >>> port = Port({'name': 'a', 'type': 'number', 'format': 'number'})
        >>> port.push({'format': 'json', 'mode': 'inline', 'data': '2'})['data']
        2

        >>> port.push({'format': 'number', 'mode': 'inline', 'data': 3})['data']
        3
        """
        _spec = data_spec

        if self.auto_validate and not self.validate(_spec):
            raise ValidationError(self, _spec)

        if self.auto_convert:
            _spec = self.convert(_spec, self.format)  # Does this still need to push?
        elif _spec['format'] == self.format:

            data = data_spec.get('script_data')  # Is this always a task output?

            io.push(data, _spec, task_output=self.spec)
        else:
            raise Exception('Expected matching data formats ({} != {})' % (
                str(_spec['format']), str(self.format)
            ))
        return _spec

__all__ = (
    'Port',
    'ValidationError'
)