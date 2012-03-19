from __future__ import with_statement
import struct
import StringIO
import io
import sys
import datetime
import re

REDIS_RDB_6BITLEN = 0
REDIS_RDB_14BITLEN = 1
REDIS_RDB_32BITLEN = 2
REDIS_RDB_ENCVAL = 3

REDIS_RDB_OPCODE_EXPIRETIME_MS = 252
REDIS_RDB_OPCODE_EXPIRETIME = 253
REDIS_RDB_OPCODE_SELECTDB = 254
REDIS_RDB_OPCODE_EOF = 255

REDIS_RDB_TYPE_STRING = 0
REDIS_RDB_TYPE_LIST = 1
REDIS_RDB_TYPE_SET = 2
REDIS_RDB_TYPE_ZSET = 3
REDIS_RDB_TYPE_HASH = 4
REDIS_RDB_TYPE_HASH_ZIPMAP = 9
REDIS_RDB_TYPE_LIST_ZIPLIST = 10
REDIS_RDB_TYPE_SET_INTSET = 11
REDIS_RDB_TYPE_ZSET_ZIPLIST = 12

REDIS_RDB_ENC_INT8 = 0
REDIS_RDB_ENC_INT16 = 1
REDIS_RDB_ENC_INT32 = 2
REDIS_RDB_ENC_LZF = 3

class RdbCallback:
    """
    A Callback to handle events as the Redis dump file is parsed.
    This callback provides a serial and fast access to the dump file.
    
    """
    def start_rdb(self):
        """
        Called once we know we are dealing with a valid redis dump file
        
        """
        pass
        
    def start_database(self, db_number):
        """
        Called to indicate database the start of database `db_number` 
        
        Once a database starts, another database cannot start unless 
        the first one completes and then `end_database` method is called
        
        Typically, callbacks store the current database number in a class variable
        
        """     
        pass
    
    def set(self, key, value, expiry):
        """
        Callback to handle a key with a string value and an optional expiry
        
        `key` is the redis key
        `value` is a string or a number
        `expiry` is a datetime object. None and can be None
        
        """
        pass
    
    def start_hash(self, key, length, expiry):
        """Callback to handle the start of a hash
        
        `key` is the redis key
        `length` is the number of elements in this hash. 
        `expiry` is a `datetime` object. None means the object does not expire
        
        After `start_hash`, the method `hset` will be called with this `key` exactly `length` times.
        After that, the `end_hash` method will be called.
        
        """
        pass
    
    def hset(self, key, field, value):
        """
        Callback to insert a field=value pair in an existing hash
        
        `key` is the redis key for this hash
        `field` is a string
        `value` is the value to store for this field
        
        """
        pass
    
    def end_hash(self, key):
        """
        Called when there are no more elements in the hash
        
        `key` is the redis key for the hash
        
        """
        pass
    
    def start_set(self, key, cardinality, expiry):
        """
        Callback to handle the start of a hash
        
        `key` is the redis key
        `cardinality` is the number of elements in this set
        `expiry` is a `datetime` object. None means the object does not expire
        
        After `start_set`, the  method `sadd` will be called with `key` exactly `cardinality` times
        After that, the `end_set` method will be called to indicate the end of the set.
        
        Note : This callback handles both Int Sets and Regular Sets
        
        """
        pass

    def sadd(self, key, member):
        """
        Callback to inser a new member to this set
        
        `key` is the redis key for this set
        `member` is the member to insert into this set
        
        """
        pass
    
    def end_set(self, key):
        """
        Called when there are no more elements in this set 
        
        `key` the redis key for this set
        
        """
        pass
    
    def start_list(self, key, length, expiry):
        """
        Callback to handle the start of a list
        
        `key` is the redis key for this list
        `length` is the number of elements in this list
        `expiry` is a `datetime` object. None means the object does not expire
        
        After `start_list`, the method `rpush` will be called with `key` exactly `length` times
        After that, the `end_list` method will be called to indicate the end of the list
        
        Note : This callback handles both Zip Lists and Linked Lists.
        
        """
        pass
    
    def rpush(self, key, value) :
        """
        Callback to insert a new value into this list
        
        `key` is the redis key for this list
        `value` is the value to be inserted
        
        Elements must be inserted to the end (i.e. tail) of the existing list.
        
        """
        pass
    
    def end_list(self, key):
        """
        Called when there are no more elements in this list
        
        `key` the redis key for this list
        
        """
        pass
    
    def start_sorted_set(self, key, length, expiry):
        """
        Callback to handle the start of a sorted set
        
        `key` is the redis key for this sorted
        `length` is the number of elements in this sorted set
        `expiry` is a `datetime` object. None means the object does not expire
        
        After `start_sorted_set`, the method `zadd` will be called with `key` exactly `length` times. 
        Also, `zadd` will be called in a sorted order, so as to preserve the ordering of this sorted set.
        After that, the `end_sorted_set` method will be called to indicate the end of this sorted set
        
        Note : This callback handles sorted sets in that are stored as ziplists or skiplists
        
        """
        pass
    
    def zadd(self, key, score, member):
        """Callback to insert a new value into this sorted set
        
        `key` is the redis key for this sorted set
        `score` is the score for this `value`
        `value` is the element being inserted
        """
        pass
    
    def end_sorted_set(self, key):
        """
        Called when there are no more elements in this sorted set
        
        `key` is the redis key for this sorted set
        
        """
        pass
    
    def end_database(self, db_number):
        """
        Called when the current database ends
        
        After `end_database`, one of the methods are called - 
        1) `start_database` with a new database number
            OR
        2) `end_rdb` to indicate we have reached the end of the file
        
        """
        pass
    
    def end_rdb(self):
        """Called to indicate we have completed parsing of the dump file"""
        pass

class RdbParser :
    """
    A Parser for Redis RDB Files
    
    This class is similar in spirit to a SAX parser for XML files.
    The dump file is parsed sequentially. As and when objects are discovered,
    appropriate methods in the callback are called. 
        
    Typical usage :
        callback = MyRdbCallback() # Typically a subclass of RdbCallback
        parser = RdbParser(callback)
        parser.parse('/var/redis/6379/dump.rdb')
    
    """
    def __init__(self, callback) :
        """
            `callback` is the object that will receive parse events
        """
        self._callback = callback
        self._key = None
        self._expiry = None

    def parse(self, filename):
        """
        Parse a redis rdb dump file, and call methods in the 
        callback object during the parsing operation.
        """
        with open(filename, "rb") as f:
            self.verify_magic_string(f.read(5))
            self.verify_version(f.read(4))
            self._callback.start_rdb()
            
            is_first_database = True
            db_number = 0
            while True :
                self._expiry = None
                data_type = read_unsigned_char(f)
                
                if data_type == REDIS_RDB_OPCODE_EXPIRETIME_MS :
                    self._expiry = to_datetime(read_unsigned_long(f))
                    data_type = read_unsigned_char(f)
                elif data_type == REDIS_RDB_OPCODE_EXPIRETIME :
                    self._expiry = to_datetime(read_unsigned_int(f) * 1000)
                    data_type = read_unsigned_char(f)
                
                if data_type == REDIS_RDB_OPCODE_SELECTDB :
                    if not is_first_database :
                        self._callback.end_database(db_number)
                    is_first_database = False
                    db_number = self.read_length(f)
                    self._callback.start_database(db_number)
                    continue
                
                if data_type == REDIS_RDB_OPCODE_EOF :
                    self._callback.end_database(db_number)
                    self._callback.end_rdb()
                    break
                
                self._key = self.read_string(f)
                self.read_object(f, data_type)

    # Read an object for the stream
    # f is the redis file 
    # enc_type is the type of object
    def read_object(self, f, enc_type) :
        if enc_type == REDIS_RDB_TYPE_STRING :
            val = self.read_string(f)
            self._callback.set(self._key, val, self._expiry)
        elif enc_type == REDIS_RDB_TYPE_LIST :
            # A redis list is just a sequence of strings
            # We successively read strings from the stream and create a list from it
            # The lists are in order i.e. the first string is the head, 
            # and the last string is the tail of the list
            length = self.read_length(f)
            self._callback.start_list(self._key, length, self._expiry)
            for count in xrange(0, length) :
                val = self.read_string(f)
                self._callback.rpush(self._key, val)
            self._callback.end_list(self._key)
        elif enc_type == REDIS_RDB_TYPE_SET :
            # A redis list is just a sequence of strings
            # We successively read strings from the stream and create a set from it
            # Note that the order of strings is non-deterministic
            length = self.read_length(f)
            self._callback.start_set(self._key, length, self._expiry)
            for count in xrange(0, length) :
                val = self.read_string(f)
                self._callback.sadd(self._key, val)
            self._callback.end_set(self._key)
        elif enc_type == REDIS_RDB_TYPE_ZSET :
            length = self.read_length(f)
            self._callback.start_sorted_set(self._key, length, self._expiry)
            for count in xrange(0, length) :
                val = self.read_string(f)
                dbl_length = read_unsigned_char(f)
                score = f.read(dbl_length)
                if isinstance(score, str):
                    score = float(score)
                self._callback.zadd(self._key, score, val)
            self._callback.end_sorted_set(self._key)
        elif enc_type == REDIS_RDB_TYPE_HASH :
            length = self.read_length(f)
            self._callback.start_hash(self._key, length, self._expiry)
            for count in xrange(0, length) :
                field = self.read_string(f)
                value = self.read_string(f)
                self._callback.hset(self._key, field, value)
            self._callback.end_hash(self._key)
        elif enc_type == REDIS_RDB_TYPE_HASH_ZIPMAP :
            self.read_zipmap(f)
        elif enc_type == REDIS_RDB_TYPE_LIST_ZIPLIST :
            self.read_ziplist(f)
        elif enc_type == REDIS_RDB_TYPE_SET_INTSET :
            self.read_intset(f)
        elif enc_type == REDIS_RDB_TYPE_ZSET_ZIPLIST :
            self.read_zset_from_ziplist(f)
        else :
            raise Exception('read_object', 'Invalid object type %d' % enc_type)

    def read_length(self, f) :
        return self.read_length_with_encoding(f)[0]

    def read_length_with_encoding(self, f) :
        length = 0
        is_encoded = False
        bytes = []
        bytes.append(read_unsigned_char(f))
        enc_type = (bytes[0] & 0xC0) >> 6
        if enc_type == REDIS_RDB_ENCVAL :
            is_encoded = True
            length = bytes[0] & 0x3F
        elif enc_type == REDIS_RDB_6BITLEN :
            length = bytes[0] & 0x3F
        elif enc_type == REDIS_RDB_14BITLEN :
            bytes.append(read_unsigned_char(f))
            length = ((bytes[0]&0x3F)<<8)|bytes[1]
        else :
            length = ntohl(f)
        return (length, is_encoded)

    def read_string(self, f) :
        tup = self.read_length_with_encoding(f)
        length = tup[0]
        is_encoded = tup[1]
        val = None
        if is_encoded :
            if length == REDIS_RDB_ENC_INT8 :
                val = read_signed_char(f)
            elif length == REDIS_RDB_ENC_INT16 :
                val = read_signed_short(f)
            elif length == REDIS_RDB_ENC_INT32 :
                val = read_signed_int(f)
            elif length == REDIS_RDB_ENC_LZF :
                clen = self.read_length(f)
                l = self.read_length(f)
                val = lzf_decompress(f.read(clen), l)
        else :
            val = f.read(length)
        return val

    def read_intset(self, f) :
        raw_string = self.read_string(f)
        buff = StringIO.StringIO(raw_string)
        encoding = read_unsigned_int(buff)
        num_entries = read_unsigned_int(buff)
        self._callback.start_set(self._key, num_entries, self._expiry)
        for x in xrange(0, num_entries) :
            if encoding == 8 :
                entry = read_unsigned_long(buff)
            elif encoding == 4 :
                entry = read_unsigned_int(buff)
            elif encoding == 2 :
                entry = read_unsigned_short(buff)
            else :
                raise Exception('read_intset', 'Invalid encoding %d' % encoding)
            self._callback.sadd(self._key, entry)
        self._callback.end_list(self._key)

    def read_ziplist(self, f) :
        raw_string = self.read_string(f)
        buff = StringIO.StringIO(raw_string)
        zlbytes = read_unsigned_int(buff)
        tail_offset = read_unsigned_int(buff)
        num_entries = read_unsigned_short(buff)
        self._callback.start_list(self._key, num_entries, self._expiry)
        for x in xrange(0, num_entries) :
            val = self.read_ziplist_entry(buff)
            self._callback.rpush(self._key, val)
        zlist_end = read_unsigned_char(buff)
        if zlist_end != 255 : 
            raise Exception('read_ziplist', "Invalid zip list end - %d" % zlist_end)
        self._callback.end_list(self._key)

    def read_zset_from_ziplist(self, f) :
        raw_string = self.read_string(f)
        buff = StringIO.StringIO(raw_string)
        zlbytes = read_unsigned_int(buff)
        tail_offset = read_unsigned_int(buff)
        num_entries = read_unsigned_short(buff)
        if (num_entries % 2) :
            raise Exception('read_zset_from_ziplist', "Expected even number of elements, but found %d" % num_entries)
        num_entries = num_entries /2
        self._callback.start_sorted_set(self._key, num_entries, self._expiry)
        for x in xrange(0, num_entries) :
            member = self.read_ziplist_entry(buff)
            score = self.read_ziplist_entry(buff)
            if isinstance(score, str) :
                score = float(score)
            self._callback.zadd(self._key, score, member)
        zlist_end = read_unsigned_char(buff)
        if zlist_end != 255 : 
            raise Exception('read_ziplist', "Invalid zip list end - %d" % zlist_end)
        self._callback.end_sorted_set(self._key)

    def read_ziplist_entry(self, f) :
        length = 0
        value = None
        prev_length = read_unsigned_char(f)
        if prev_length == 254 :
            prev_length = read_unsigned_int(f)
        entry_header = read_unsigned_char(f)
        if (entry_header >> 6) == 0 :
            length = entry_header & 0x3F
            value = f.read(length)
        elif (entry_header >> 6) == 1 :
            length = ((entry_header & 0x3F) << 8) | read_unsigned_char(f)
            value = f.read(length)
        elif (entry_header >> 6) == 2 :
            length = read_unsigned_int(f)
            value = f.read(length)
        elif (entry_header >> 4) == 12 :
            value = read_signed_short(f)
        elif (entry_header >> 4) == 13 :
            value = read_signed_int(f)
        elif (entry_header >> 4) == 14 :
            value = read_signed_long(f)
        else :
            raise Exception('read_ziplist_entry', 'Invalid entry_header %d' % entry_header)
        return value
        
    def read_zipmap(self, f) :
        raw_string = self.read_string(f)
        buff = io.BytesIO(bytearray(raw_string))
        num_entries = read_unsigned_char(buff)
        
        self._callback.start_hash(self._key, num_entries, self._expiry)
        while True :
            next_length = self.read_zipmap_next_length(buff)
            if next_length is None :
                break
            key = buff.read(next_length)
            next_length = self.read_zipmap_next_length(buff)
            if next_length is None :
                raise Exception('read_zip_map', 'Unexepcted end of zip map')        
            free = read_unsigned_char(buff)
            value = buff.read(next_length)
            skip(buff, free)
            self._callback.hset(self._key, key, value)
        self._callback.end_hash(self._key)

    def read_zipmap_next_length(self, f) :
        num = read_unsigned_char(f)
        if num <= 252 :
            return num
        elif num == 253 :
            return read_unsigned_int(f)
        elif num == 254 :
            raise Exception('read_zipmap_next_length', 'Unexpected value in length field - %d' % num)
        else :
            return None

    def verify_magic_string(self, magic_string) :
        if magic_string != 'REDIS' :
            raise Exception('verify_magic_string', 'Invalid File Format')

    def verify_version(self, version_str) :
        version = int(version_str)
        if version < 1 or version > 3 : 
            raise Exception('verify_version', 'Invalid RDB version number %d' % version)


def skip(f, free):
    if free :
        f.read(free)

def lzf_decompress(compressed, expected_length):
    in_stream = bytearray(compressed)
    in_len = len(in_stream)
    in_index = 0
    out_stream = bytearray()
    out_index = 0

    while in_index < in_len :
        ctrl = in_stream[in_index]
        if not isinstance(ctrl, int) :
            raise Exception('lzf_decompress', 'ctrl should be a number %s' % str(ctrl))
        in_index = in_index + 1
        if ctrl < 32 :
            for x in xrange(0, ctrl + 1) :
                out_stream.append(in_stream[in_index])
                #sys.stdout.write(chr(in_stream[in_index]))
                in_index = in_index + 1
                out_index = out_index + 1
        else :
            length = ctrl >> 5
            if length == 7 :
                length = length + in_stream[in_index]
                in_index = in_index + 1
            
            ref = out_index - ((ctrl & 0x1f) << 8) - in_stream[in_index] - 1
            in_index = in_index + 1
            for x in xrange(0, length + 2) :
                out_stream.append(out_stream[ref])
                ref = ref + 1
                out_index = out_index + 1
    if len(out_stream) != expected_length :
        raise Exception('lzf_decompress', 'Expected lengths do not match %d != %d' % (len(out_stream), expected_length))
    return str(out_stream)

def ntohl(f) :
    val = read_unsigned_int(f)
    new_val = 0
    new_val = new_val | ((val & 0x000000ff) << 24)
    new_val = new_val | ((val & 0xff000000) >> 24)
    new_val = new_val | ((val & 0x0000ff00) << 8)
    new_val = new_val | ((val & 0x00ff0000) >> 8)
    return new_val

def to_datetime(usecs_since_epoch):
    seconds_since_epoch = usecs_since_epoch / 1000000
    useconds = usecs_since_epoch % 1000000
    dt = datetime.datetime.fromtimestamp(seconds_since_epoch)
    delta = datetime.timedelta(microseconds = useconds)
    return dt + delta
    
def read_signed_char(f) :
    return struct.unpack('b', f.read(1))[0]
    
def read_unsigned_char(f) :
    return struct.unpack('B', f.read(1))[0]

def read_signed_short(f) :
    return struct.unpack('h', f.read(2))[0]
        
def read_unsigned_short(f) :
    return struct.unpack('H', f.read(2))[0]

def read_signed_int(f) :
    return struct.unpack('i', f.read(4))[0]
    
def read_unsigned_int(f) :
    return struct.unpack('I', f.read(4))[0]

def read_signed_long(f) :
    return struct.unpack('q', f.read(8))[0]
    
def read_unsigned_long(f) :
    return struct.unpack('Q', f.read(8))[0]

def string_as_hexcode(string) :
    for s in string :
        if isinstance(s, int) :
            print(hex(s))
        else :
            print(hex(ord(s)))


class DebugCallback(RdbCallback) :
    def start_rdb(self):
        print('[')
    
    def start_database(self, db_number):
        print('{')
    
    def set(self, key, value, expiry):
        print('"%s" : "%s"' % (str(key), str(value)))
    
    def start_hash(self, key, length, expiry):
        print('"%s" : {' % str(key))
        pass
    
    def hset(self, key, field, value):
        print('"%s" : "%s"' % (str(field), str(value)))
    
    def end_hash(self, key):
        print('}')
    
    def start_set(self, key, cardinality, expiry):
        print('"%s" : [' % str(key))

    def sadd(self, key, member):
        print('"%s"' % str(member))
    
    def end_set(self, key):
        print(']')
    
    def start_list(self, key, length, expiry):
        print('"%s" : [' % str(key))
    
    def rpush(self, key, value) :
        print('"%s"' % str(value))
    
    def end_list(self, key):
        print(']')
    
    def start_sorted_set(self, key, length, expiry):
        print('"%s" : {' % str(key))
    
    def zadd(self, key, score, member):
        print('"%s" : "%s"' % (str(member), str(score)))
    
    def end_sorted_set(self, key):
        print('}')
    
    def end_database(self, db_number):
        print('}')
    
    def end_rdb(self):
        print(']')


