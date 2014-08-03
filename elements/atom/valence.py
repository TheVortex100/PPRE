
import struct

from rawdb.elements.atom.packer import Packer
from rawdb.elements.atom.data import DataConsumer
from rawdb.util import temporary_attr


VALUE_ZERO_FUNC = lambda atomic: 0


class ValenceFormatter(Packer):
    """Formatter that extends struct's functionality

    Methods
    -------
    pack_one : function
        Takes a value and formats it to a string
    unpack_one : function
        Takes a string and pulls out the value and remaining string from it.
        If value is None, it should not be considered.

    Attributes
    ----------
    format_char : string
        Struct format string for field
    count : int or function(atomic)
        Array length for field
    terminator : int
        Array terminator value
    subatomic : type
        AtomicInstance type for creating subatoms
    ignore : bool
        If set to True, do not add to Atomic attributes (ex, padding)
    """
    valid_params = ['value']

    def __init__(self, name, format_char=None, array_item=None,
                 sub_formats=None):
        self.name = name
        self.format_char = format_char
        self.array_item = array_item
        self.sub_formats = sub_formats
        if format_char is not None:
            self.unpack_one = self.unpack_char
            self.pack_one = self.pack_char
        elif array_item is not None:
            self.formatter = array_item
            self.unpack_one = self.unpack_array
            self.pack_one = self.pack_array
        elif sub_formats is not None:
            self.unpack_one = self.unpack_multi
            self.pack_one = self.pack_multi
        self.ignore = False
        self.params = {}

    def set_param(self, key, value):
        if key in self.valid_params:
            self.params[key] = value
        else:
            raise ValueError('%s is not a valid parameter' % key)

    def get_param(self, key, atomic):
        value = self.params[key]
        if hasattr(value, '__call__'):
            return value(atomic)
        return value

    def get_value(self, atomic):
        return atomic[self.name]

    def set_value(self, atomic, value):
        atomic[self.name] = value

    def copy(self):
        kwargs = dict(name=self.name, format_char=self.format_char)
        if self.array_item:
            kwargs['array_item'] = self.array_item.copy()
        if self.sub_formats:
            kwargs['sub_formats'] = [entry.copy()
                                     for entry in self.sub_formats]
        new_formatter = ValenceFormatter(**kwargs)
        for attr, value in self.__dict__.items():
            if attr in ['subatomic'] or not hasattr(value, '__call__'):
                setattr(new_formatter, attr, value)
        return new_formatter

    def identity(self):
        return id(self)

    def format_iterator(self, atomic):
        return self.sub_formats

    def unpack_char(self, atomic):
        """Unpacks the format_char string from atomic.data

        If self.format_char is a function, this will be called with atomic as
        the first argument to generate the format string
        """
        try:
            format_char = self.format_char(atomic)
        except:
            format_char = self.format_char
        if not format_char.strip('x'):
            value = None
            consume = len(format_char)
            atomic.data.consume(consume)
        else:
            consume = struct.calcsize(format_char)
            value = struct.unpack(format_char, atomic.data[:consume])[0]
        return value

    def pack_char(self, atomic):
        # TODO: format_char as function
        if not self.format_char.strip('x'):
            data = struct.pack(self.format_char)
        else:
            data = struct.pack(self.format_char, self.get_value(atomic))
        return data

    def unpack_array(self, atomic):
        total = 0
        arr = []
        try:
            count = self.count(atomic)
        except:
            count = self.count
        try:
            terminator = self.terminator(atomic)
        except:
            terminator = self.terminator
        while 1:
            if count is not None and total >= count:
                break
            value = self.formatter.unpack_one(atomic)
            if terminator is not None \
                    and value == terminator:
                break
            arr.append(value)
            total += 1
        return arr

    def pack_array(self, arr):
        data = ''
        for value in arr:
            data += self.formatter.pack_one(value)
        if self.terminator is not None:
            data += self.formatter.pack_one(self.terminator)
        # TODO: count validation
        return data

    def unpack_multi(self, atomic):
        data = DataConsumer(atomic.data)
        unpacked = {}
        subatomic = self.subatomic(self, data)
        for entry in self.format_iterator(subatomic):
            value = entry.unpack_one(subatomic)
            if not entry.ignore:
                subatomic[entry.name] = value
        subatomic.freeze()
        atomic.data.consume(subatomic.data.exhausted)
        return subatomic

    def pack_multi(self, atomic):
        return str(atomic)


class ValencePadding(ValenceFormatter):
    """Padding

    Parameters
    ----------
    length : int
        How many characters the padding should be
    align : int
        What offset the data must align to after adding padded length
    pad_string : string
        Characters to pad on. Last characters get removed if they do not fit.
    """
    def __init__(self, length=0, pad_string='\x00', align=0):
        super(ValencePadding, self).__init__(None)
        self.length = length
        self.pad_string = pad_string
        self.align = align

    def unpack_one(self, atomic):
        atomic.data.offset += self.length
        return None

    def pack_one(self, atomic):
        offset = end = atomic.data.offset
        end += self.length
        if self.align:
            if end % self.align:
                end += self.align - (end % self.align)
        data = self.pad_string*((end-offset)/len(self.pad_string)+1)
        return data[:end-offset]


class ValenceShell(ValenceFormatter):
    """Combines two ValenceFormatters"""
    OP_ADD = 1
    OP_SUBTRACT = 2

    def __init__(self, one, *others):
        self.first = one
        self.others = others

    def _get_value(self, sub_format, atomic):
        try:
            return sub_format.get_value(atomic)
        except:
            return sub_format

    def get_value(self, atomic):
        value = self.first.get_value(atomic)
        for sub, operation in self.others:
            if operation == self.OP_ADD:
                value += self._get_value(sub, atomic)
            elif operation == self.OP_SUBTRACT:
                value -= self._get_value(sub, atomic)


class SubValenceWrapper(object):
    def __init__(self, base, target):
        super(SubValenceWrapper, self).__setattr__('_base', base)
        super(SubValenceWrapper, self).__setattr__('_target', target)

    def get_atomic(self, atomic, namespace):
        while atomic._namespace != namespace:
            atomic = atomic[namespace[len(atomic._namespace)]]
        return atomic

    def __getattr__(self, name):
        target_attr = getattr(self._target, name)
        if hasattr(target_attr, '__call__'):

            def target_func(*args, **kwargs):
                func_code = target_attr.func_code
                argnames = list(func_code.co_varnames[0:func_code.co_argcount])
                try:
                    argnames.remove('self')
                except:
                    pass
                kwargs.update(dict(zip(argnames, args)))
                if 'atomic' in kwargs:
                    # FIXME
                    # This works as long as there are no collisions of names
                    # It pulls the subatom out, then it tries the actual
                    kwargs['atomic'] = self.get_atomic(kwargs['atomic'],
                                                       self._base.namespace)
                return target_attr(**kwargs)
            target_func.func_dict = target_attr.func_dict
            return target_func
        return target_attr

    def __setattr__(self, name, value):
        setattr(self._target, name, value)


class ValenceMulti(ValenceFormatter):
    """Multiple SubValence container Valence

    For grouping multiple valences together

    Parameters
    ----------
    sub_valences : list(ValenceFormatter)
        List of contained ValenceFormatters
    """
    valid_params = ValenceFormatter.valid_params+['sub_valences']

    def __init__(self, name, sub_valences, namespace):
        super(ValenceMulti, self).__init__(name)
        self.sub_valences = sub_valences
        self.namespace = namespace

    def format_iterator(self, atomic):
        return self.sub_valences

    def unpack_one(self, atomic):
        data = DataConsumer(atomic.data)
        unpacked = {}
        subatomic = self.subatomic(self, data, namespace=self.namespace)
        for entry in self.format_iterator(subatomic):
            value = entry.unpack_one(subatomic)
            if entry.name:
                subatomic[entry.name] = value
        subatomic.freeze()
        atomic.data.consume(subatomic.data.exhausted)
        return subatomic

    def pack_one(self, atomic):
        value = self.get_value(atomic)
        with temporary_attr(value, '_data', atomic.data, True):
            str(value)
            return ''

    def __getattr__(self, name):
        for entry in self.sub_valences:
            if entry.name == name:
                return SubValenceWrapper(self, entry)
        return super(ValenceMulti, self).__getattr__(name)


class ValenceArray(ValenceFormatter):
    valid_params = ValenceFormatter.valid_params + \
        ['sub_valence', 'count', 'terminator']

    def __init__(self, name, sub_valence, count=None, terminator=None):
        super(ValenceArray, self).__init__(name)
        self.sub_valence = sub_valence
        try:
            self._get_count = count.get_value
            count.get_value = self.get_count
        except AttributeError:
            self._get_count = lambda atomic: count
        self.set_param('terminator', terminator)

    def _get_count(self, atomic):
        return None

    def get_count(self, atomic):
        """Gets the number of entries of the stored value

        Returns
        -------
        count : int
            Number of entries
        count : None
            No limit found yet
        """
        try:
            return len(self.get_value(atomic))
        except:
            return self._get_count(atomic)

    def unpack_one(self, atomic):
        total = 0
        arr = []
        count = self.get_count(atomic)
        terminator = self.get_param('terminator', atomic)
        while 1:
            if count is not None and total >= count:
                break
            value = self.sub_valence.unpack_one(atomic)
            if terminator is not None \
                    and value == terminator:
                break
            arr.append(value)
            total += 1
        return arr

    def pack_one(self, atomic):
        data = ''
        terminator = self.get_param('terminator', None)
        for value in self.get_value(atomic):
            self.sub_valence.get_value = lambda atomic: value
            data += self.sub_valence.pack_one(value)
        if terminator is not None:
            self.sub_valence.get_value = lambda atomic: terminator
            data += self.sub_valence.pack_one(terminator)
        # TODO: count validation
        return data


class ValenceSeek(ValenceFormatter):
    def __init__(self, offset, start=None):
        super(ValenceSeek, self).__init__(None)
        try:
            self._get_offset = offset.get_value
            offset.get_value = lambda atomic: 0
            tmp_pack1 = offset.pack_one

            def pack_one(atomic):
                if pack_one.update:
                    atomic.data.seek_map[offset.identity()] = \
                        atomic.data.offset
                return tmp_pack1(atomic)
            offset.pack_one = pack_one
            offset.pack_one.update = True
            self.offset_valence = offset
        except AttributeError:
            self._get_offset = lambda atomic: offset
        try:
            # TODO: Check memory leaking in atomic.data
            tmp_unpack = start.unpack_one
            tmp_pack2 = start.pack_one

            def unpack_one(atomic):
                atomic.data.seek_map[start.identity()] = atomic.data.offset
                return tmp_unpack(atomic)

            def pack_one(atomic):
                if pack_one.update:
                    atomic.data.seek_map[start.identity()] = \
                        atomic.data.offset
                return tmp_pack2(atomic)
            start.unpack_one = unpack_one
            start.pack_one = pack_one
            start.pack_one.update = True
            self._get_start = lambda atomic: atomic.data.seek_map[
                start.identity()]
        except AttributeError:
            self._get_start = lambda atomic: start

    def get_offset(self, atomic):
        return self._get_offset(atomic)

    def get_write_offset(self, atomic):
        return None

    def get_start(self, atomic):
        return self._get_start(atomic)

    def unpack_one(self, atomic):
        start = self.get_start(atomic)
        if start is not None:
            atomic.data.offset = start+self.get_offset(atomic)
        else:
            atomic.data.offset += self.get_offset(atomic)

    def pack_one(self, atomic):
        # TODO: if offset is static, pad to start+offset.
        self.offset_valence.get_value = lambda atomic: atomic.data.offset - \
            self.get_start(atomic)
        print(atomic.data.seek_map, self.offset_valence.identity(), id(self.offset_valence))
        with temporary_attr(self.offset_valence.pack_one, 'update', False):
            atomic.data[atomic.data.seek_map[self.offset_valence.identity()]] = \
                self.offset_valence.pack_one(atomic)
        self.offset_valence.get_value = VALUE_ZERO_FUNC
        return ''
