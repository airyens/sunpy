"""
This module provides a wrapper around the Helioviewer API.

Keith 2011/06/26:
  
Because the current Helioviewer.org API has been optimized for us in web
applications, the currently provided methods are not ideal for use by
SunPy. For example, an ideal usage would be to request an image and get
read the result into a Map object. This requires both the image data,
without any colormap applied, and the header information, preferably either
in its original form or as a dictionary.

In order to achieve this using the current API, you would be required to
make at least three requests: the first one (getClosestImage) will find
the best match for the requested date. Next, you would need to fetch the
image data (e.g. getJP2Image) and header information (getJP2Header)
separately. Finally, once you have all of that you need to convert the
image to a bitmap and read it into an ndarray and convert the XML header 
response to a dict.

Ideally, the solution to this would be to add support to SunPy for working
with JPEG 2000 images directly. Because of the lack of support for JPEG 2000
in Python, however, this would likely require a significant amount of work,
such as writing a wrapper around the OpenJPEG library. An alternative solution
might be to add a new method to the Helioviewer API which returns the header
information (as a dictionary) and a URL or id which can be used to retrieve
the image data.
"""
from __future__ import absolute_import

#pylint: disable=E1101,F0401,W0231
__author__ = ["Keith Hughitt"]
__email__ = "keith.hughitt@nasa.gov"

import os
import json
import urllib
import urllib2
from sunpy.util import util

# Helioviewer API URL
__BASE_API_URL__ = "http://helioviewer.org/api/"

def get_data_sources(**kwargs):
    """Returns a structured list of datasources available at Helioviewer.org"""
    params = {"action": "getDataSources"}
    params.update(kwargs)
    
    return json.loads(_request(params))    

def get_closest_image(date, observatory, instrument, detector, measurement):
    """Finds the closest image available for the specified source and date.
    
    For more information on what types of requests are available and the
    expected usage for the response, consult the Helioviewer API documenation:
        http://helioviewer.org/api
    
    Parameters
    ----------
    date : mixed
        A string or datetime object for the desired date of the image
    observatory : string
        The observatory to match
    instrument : string
        The instrument to match
    detector : string
        The detector to match
    measurement : string
        
    Returns
    -------
    out : dict A dictionary including the following information:
        filepath
        filename
        date
        scale
        width
        height
        sunCenterX
        sunCenterY
        
    Examples
    --------
    >>> 
    """
    # TODO 06/26/2011 Input validation
    params = {
        "date": util.anytim(date),
        "observatory": observatory,
        "instrument": instrument,
        "detector": detector,
        "measurement": measurement
    }
    return _request(params)

def get_jp2_image(date, directory=None, **kwargs):
    """
    Downloads the JPEG 2000 that most closely matches the specified time and 
    data source.
    
    Parameters
    ----------
    date : mixed
        A string or datetime object for the desired date of the image
        
    Returns
    -------
    string : The filepath to the JP2 image or a URL if the jpip parameter was
        set to True.
    """
    params = {
        "action": "getJP2Image",
        "date": util.anytim(date).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + "Z"
    }
    params.update(kwargs)
    
    # Submit request
    response = urllib2.urlopen(__BASE_API_URL__, urllib.urlencode(params))
    
    # JPIP URL response
    if 'jpip' in kwargs:
        return response.read()
    
    # JPEG 2000 image response
    if directory is None:
        import tempfile
        directory = tempfile.gettempdir()
    
    filename = response.info()['Content-Disposition'][22:-1]
    filepath = os.path.join(directory, filename)
    
    f = open(filepath, 'wb')
    f.write(response.read())
    
    return filepath

def _request(params):
    """Sends an API request and returns the result
    
    Parameters
    ----------
    params : dict
        Parameters to send
        
    Returns
    -------
    out : String containing the result of the request
    """
    response = urllib2.urlopen(__BASE_API_URL__, urllib.urlencode(params))
        
    return response.read()

# Keith 2011/06/26: this will eventually be moved to the utilities module
# http://code.activestate.com/recipes/410469-xml-as-dictionary/
try:
    import cElementTree as ElementTree #pylint: disable=W0611
except ImportError:
    import xml.etree.ElementTree as ElementTree #pylint: disable=W0404

class XmlListConfig(list):
    def __init__(self, aList):
        for element in aList:
            if element:
                # treat like dict
                if len(element) == 1 or element[0].tag != element[1].tag:
                    self.append(XmlDictConfig(element))
                # treat like list
                elif element[0].tag == element[1].tag:
                    self.append(XmlListConfig(element))
            elif element.text:
                text = element.text.strip()
                if text:
                    self.append(text)


class XmlDictConfig(dict):
    '''
    Example usage:

    >>> tree = ElementTree.parse('your_file.xml')
    >>> root = tree.getroot()
    >>> xmldict = XmlDictConfig(root)

    Or, if you want to use an XML string:

    >>> root = ElementTree.XML(xml_string)
    >>> xmldict = XmlDictConfig(root)

    And then use xmldict for what it is... a dict.
    '''
    def __init__(self, parent_element):
        if parent_element.items():
            self.update(dict(parent_element.items()))
        for element in parent_element:
            if element:
                # treat like dict - we assume that if the first two tags
                # in a series are different, then they are all different.
                if len(element) == 1 or element[0].tag != element[1].tag:
                    aDict = XmlDictConfig(element)
                # treat like list - we assume that if the first two tags
                # in a series are the same, then the rest are the same.
                else:
                    # here, we put the list in dictionary; the key is the
                    # tag name the list elements all share in common, and
                    # the value is the list itself 
                    aDict = {element[0].tag: XmlListConfig(element)}
                # if the tag has attributes, add those to the dict
                if element.items():
                    aDict.update(dict(element.items()))
                self.update({element.tag: aDict})
            # this assumes that if you've got an attribute in a tag,
            # you won't be having any text. This may or may not be a 
            # good idea -- time will tell. It works for the way we are
            # currently doing XML configuration files...
            elif element.items():
                self.update({element.tag: dict(element.items())})
            # finally, if there are no child tags and no attributes, extract
            # the text
            else:
                self.update({element.tag: element.text})
