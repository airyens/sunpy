"""
MapHeader is a generalized header class that deals with header parsing and
normalization.
"""
from __future__ import absolute_import

class MapHeader(dict):
    """
    MapHeader(header)
    
    A dictionary-like class for working with FITS, etc headers
    
    Parameters
    ----------
    header : pyfits.core.Header, dict
        Header tags associated with the data
        
    Attributes
    ----------
    
    """
    def __init__(self, *args, **kwargs):
        """Creates a new MapHeader instance"""
        if isinstance(args[0], basestring):
            # filepath
            from sunpy.io import read_header
            tags = read_header(args[0])
        else:
            # dictionary
            tags = args[0]

        # Store all keys as upper-case to allow for case-insensitive indexing
        tags = dict((k.upper(), v) for k, v in tags.items())
        args = (tags,) + args[1:]

        dict.__init__(self, *args, **kwargs)            
            
    def __contains__(self, key):
        """Overide __contains__"""
        return dict.__contains__(self, key.upper())
            
    def __getitem__(self, key):
        """Overide [] indexing"""
        return dict.__getitem__(self, key.upper())
    
    def __setitem__(self, key, value):
        """Overide [] indexing"""
        return dict.__setitem__(self, key.upper(), value)
    
    def copy(self):
        """Overide copy operator"""
        return type(self)(dict.copy(self))
    
    def get(self, key, default=None):
        """Overide .get() indexing"""
        return dict.get(self, key.upper(), default)
    
    def has_key(self, key):
        """Overide .has_key() to perform case-insensitively"""
        return dict.has_key(self, key.upper())
    
    def pop(self, key, default=None):
        """Overide .pop() to perform case-insensitively"""
        return dict.pop(self, key.upper(), default)
    
    def update(self, dict2):
        """Overide .update() to perform case-insensitively"""
        return dict.update(self, dict((k.upper(),v) for k,v in dict2.items()))

    def setdefault(self, key, default=None):
        """Overide .setdefault() to perform case-insensitively"""
        return dict.setdefault(self, key.upper(), default)
        