import collections

import abc
import copy
import six
import yaml

from lymph.utils import import_object, Undefined
from lymph.exceptions import ConfigurationError


@six.add_metaclass(abc.ABCMeta)
class ConfigObject(collections.Mapping):

    @abc.abstractmethod
    def get(self, key, default=None):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_raw(self, key, default=None):
        raise NotImplementedError()

    @abc.abstractmethod
    def set(self, key, value):
        raise NotImplementedError()

    def __getitem__(self, key):
        return self.get(key)

    def setdefault(self, key, default):
        value = self.get(key)
        if value is None:
            self.set(key, default)
            return default
        return value

    def create_instance(self, key, default_class=None, **kwargs):
        instance_config = self.get(key, {})
        return self._create_instance(key, instance_config, default_class=default_class, **kwargs)

    def _create_instance(self, key, instance_config, default_class=None, **kwargs):
        if instance_config is None:
            raise ConfigurationError("no config available for %r" % key)

        clspath = instance_config.get('class', default_class)
        if clspath is None:
            raise ConfigurationError("no config available for %r (or no class configured)" % key)

        cls = import_object(clspath)
        if hasattr(cls, 'from_config'):
            return cls.from_config(instance_config, **kwargs)
        else:
            instance_config = copy.deepcopy(dict(instance_config))
            del instance_config['class']
            instance_config.update(kwargs)
            return cls(**instance_config)

    def get_instance(self, key, default_class=None, **kwargs):
        instance_data = self.get(key)
        if isinstance(instance_data, six.string_types) and instance_data.startswith('dep:'):
            _, dep_name = instance_data.split(':', 1)
            return self.get_dependency(dep_name, **kwargs)

        instance = self.root._instances_cache.get(key)
        if not instance:
            instance = self._create_instance(
                key, instance_data, default_class=default_class, **kwargs)
            self.root._instances_cache[key] = instance
        return instance

    def get_dependency(self, key, **kwargs):
        return self.root.get_instance('dependencies.%s' % key, **kwargs)


class ConfigView(ConfigObject):
    def __init__(self, config, path):
        self.root = config
        self.path = path

    def __len__(self):
        return len(self.root.get_raw(self.path))

    def get_raw(self, key, default=None):
        return self.root.get_raw('%s.%s' % (self.path, key), default)

    def get(self, key, default=None):
        return self.root.get('%s.%s' % (self.path, key), default)

    def set(self, key, value):
        return self.root.set('%s.%s' % (self.path, key), value)

    def __iter__(self):
        return iter(self.root.get_raw(self.path))

    def __str__(self):
        return '%s -> %r' % (self.path, self.root)

    def __repr__(self):
        return '%s(%r, %r)' % (self.__class__.__name__, self.root, self.path)


class Configuration(ConfigObject):
    def __init__(self, values=None):
        self.values = values or {}
        self._instances_cache = {}

    def __iter__(self):
        return iter(self.values)

    def __len__(self):
        return len(self.values)

    @property
    def root(self):
        return self

    def load_file(self, filename, sections=None):
        with open(filename, 'r') as f:
            self.load(f, sections=sections)

    def load(self, f, sections=None):
        for section, values in six.iteritems(yaml.load(f)):
            if sections is None or section in sections:
                if section in self.values:
                    self.values[section].update(values)
                else:
                    self.values[section] = values

    def update(self, data):
        self.values.update(data)

    def set(self, key, data):
        path = key.split('.')
        values = self.values
        for bit in path[:-1]:
            new_values = values.setdefault(bit, {})
            if new_values is None:
                values[bit] = {}
                values = values[bit]
            else:
                values = new_values
        values[path[-1]] = data

    def get_raw(self, key, default=Undefined):
        path = key.split('.')
        values = self.values
        for bit in path[:-1]:
            values = values[bit]
            if values is None:
                if default is not Undefined:
                    return default
                raise KeyError(key)
        try:
            return values[path[-1]]
        except KeyError:
            if default is not Undefined:
                return default
            raise KeyError(key)

    def get(self, key, default=None):
        try:
            value = self.get_raw(key)
        except KeyError:
            return default
        if isinstance(value, dict):
            value = ConfigView(self, key)
        return value

    def __str__(self):
        return str(self.values)

    def __repr__(self):
        return "lymph.config.Configuration(values={values})".format(
            values=self.values)
