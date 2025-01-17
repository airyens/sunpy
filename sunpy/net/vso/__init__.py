# -*- coding: utf-8 -*-
# Author: Florian Mayer <florian.mayer@bitsrc.org>

#pylint: disable=W0401,C0103,R0904,W0141

from __future__ import absolute_import

"""
This module provides a wrapper around the VSO API.
"""

import re
import os
import sys
import tempfile
import threading

from datetime import datetime, timedelta
from functools import partial
from collections import defaultdict

from suds import client, TypeNotFound

from sunpy.net import download
from sunpy.net.attr import and_, Attr
from sunpy.net.vso.attrs import walker, TIMEFORMAT
from sunpy.util.util import anytim, to_angstrom, print_table

DEFAULT_URL = 'http://docs.virtualsolar.org/WSDL/VSOi_rpc_literal.wsdl'
DEFAULT_PORT = 'nsoVSOi'
RANGE = re.compile(r'(\d+)(\s*-\s*(\d+))?(\s*([a-zA-Z]+))?')


# TODO: Name
class NoData(Exception):
    """ Risen for callbacks of VSOClient that are unable to supply
    information for the request. """
    pass


class _Str(str):
    """ Subclass of string that contains a meta attribute for the
    record_item associated with the file. """
    pass


# ----------------------------------------

class Results(object):
    """ Returned by VSOClient.get. Use .wait to wait
    for completion of download.
    """
    def __init__(self, callback, n=0, done=None):
        self.callback = callback
        self.n = n
        self.map_ = {}
        self.done = done
        self.evt = threading.Event()
        self.errors = []
    
    def submit(self, keys, value):
        for key in keys:
            self.map_[key] = value
        self.poke()
    
    def poke(self):
        self.n -= 1
        if not self.n:
            if self.done is not None:
                self.map_ = self.done(self.map_)
            self.callback(self.map_)
            self.evt.set()
    
    def require(self, keys):
        self.n += 1
        return partial(self.submit, keys)
    
    def wait(self):
        """ Wait for result to be complete and return it. """
        self.evt.wait()
        return self.map_
    
    def add_error(self, exception):
        self.errors.append(exception)
        self.poke()


def _parse_waverange(string):
    min_, max_, unit = RANGE.match(string)[::2]
    return {
        'wave_wavemin': min_,
        'wave_wavemax': min_ if max_ is None else max_,
        'wave_waveunit': 'Angstrom' if unit is None else unit,
    }


def _parse_date(string):
    start, end = string.split(' - ')
    return {'time_start': start.strip(), 'time_end': end.strip()}


def iter_records(response):
    for prov_item in response.provideritem:
        if not hasattr(prov_item, 'record') or not prov_item.record:
            continue
        for record_item in prov_item.record.recorditem:
            yield record_item


def iter_errors(response):
    for prov_item in response.provideritem:
        if not hasattr(prov_item, 'record') or not prov_item.record:
            yield prov_item


class QueryResponse(list):
    def __init__(self, lst, queryresult=None):
        super(QueryResponse, self).__init__(lst)
        self.queryresult = queryresult
        self.errors = []
    
    @classmethod
    def create(cls, queryresult):
        return cls(iter_records(queryresult), queryresult)
    
    def total_size(self):
        """ Total size of data in KB. May be less than the actual
        size because of inaccurate data providers. """
        # Warn about -1 values?
        return sum(record.size for record in self if record.size > 0)
    
    def num_records(self):
        """ Return number of records. """
        return len(self)
    
    def time_range(self):
        """ Return total time-range all records span across. """
        return (
            datetime.strptime(
                min(record.time.start for record in self), TIMEFORMAT),
            datetime.strptime(
                max(record.time.end for record in self), TIMEFORMAT)
        )

    def show(self):
        """Print out human-readable summary of records retreived"""

        table = [[str(datetime.strptime(record.time.start, TIMEFORMAT)), 
          str(datetime.strptime(record.time.end, TIMEFORMAT)), 
          record.source,
          record.instrument,
          record.extent.type] for record in self]
        table.insert(0, ['----------','--------','------','----------','----'])        
        table.insert(0, ['Start time','End time','Source','Instrument','Type'])

        print(print_table(table, colsep = '  ', linesep='\n'))
            
    def add_error(self, exception):
        self.errors.append(exception)

class DownloadFailed(Exception):
    pass

class MissingInformation(Exception):
    pass

class UnknownMethod(Exception):
    pass

class MultipleChoices(Exception):
    pass

class UnknownVersion(Exception):
    pass

class UnknownStatus(Exception):
    pass

class VSOClient(object):
    """ Main VSO Client. """
    method_order = [
        'URL-TAR_GZ', 'URL-ZIP', 'URL-TAR', 'URL-FILE', 'URL-packaged'
    ]
    def __init__(self, api=None):
        if api is None:
            api = client.Client(DEFAULT_URL)
            api.set_options(port=DEFAULT_PORT)
        self.api = api
    
    def make(self, type_, **kwargs):
        obj = self.api.factory.create(type_)
        for k, v in kwargs.iteritems():
            split = k.split('__')
            tip = split[-1]
            rest = split[:-1]
            
            item = obj
            for elem in rest:
                item = item[elem]
            
            if isinstance(v, dict):
                # Do not throw away type information for dicts.
                for k, v in v.iteritems():
                    item[tip][k] = v
            else:
                item[tip] = v
        return obj
    
    def query(self, *query):
        """ Query data from the VSO with the new API. Takes a variable number
        of attributes as parameter, which are chained together using AND.
        
        The new query language allows complex queries to be easily formed.
        
        Examples
        --------
        Query all data from eit or aia between 2010-01-01T00:00 and
        2010-01-01T01:00.
        
        >>> client.query(
        ...    vso.Time(datetime(2010, 1, 1), datetime(2010, 1, 1, 1)),
        ...    vso.Instrument('eit') | vso.Instrument('aia')
        ... )
        
        Returns
        -------
        out : :py:class:`QueryResult` (enhanced list) of matched items. Return value of same type as the one of :py:meth:`VSOClient.query`.
        """
        query = and_(*query)
        
        responses = []
        for block in walker.create(query, self.api):
            try:
                responses.append(
                    self.api.service.Query(
                        self.make('QueryRequest', block=block)
                    )
                )
            except TypeNotFound:
                pass
            except Exception as ex:
                response = QueryResponse.create(self.merge(responses))
                response.add_error(ex)
        
        return QueryResponse.create(self.merge(responses))
    
    def merge(self, queryresponses):
        if len(queryresponses) == 1:
            return queryresponses[0]
        
        fileids = set()
        providers = {}
        
        for queryresponse in queryresponses:
            for provideritem in queryresponse.provideritem:
                provider = provideritem.provider
                if not hasattr(provideritem, 'record'):
                    continue
                if not hasattr(provideritem.record, 'recorditem'):
                    continue
                if not provideritem.provider in providers:
                    providers[provider] = provideritem
                    fileids |= set(
                        record_item.fileid
                        for record_item in provideritem.record.recorditem
                    )
                else:
                    for record_item in provideritem.record.recorditem:
                        if record_item.fileid not in fileids:
                            fileids.add(record_item.fileid)
                            providers[provider].record.recorditem.append(
                                record_item
                            )
                            providers[provider].no_of_records_found += 1
                            providers[provider].no_of_records_returned += 1
        return self.make('QueryResponse', provideritem=providers.values())
    
    @staticmethod
    def mk_filename(pattern, response, sock, url):
        # FIXME: os.path.exists(name)
        name = sock.headers.get(
            'Content-Disposition', url.rstrip('/').rsplit('/', 1)[-1]
        )
        if not name:
            name = response.fileid.replace('/', '_')
        
        fname = pattern.format(file=name, **dict(response))
        dir_ = os.path.dirname(fname)
        if not os.path.exists(dir_):
            os.makedirs(dir_)
        return fname
    
    # pylint: disable=R0914
    def query_legacy(self, tstart=None, tend=None, **kwargs):
        """
        Query data from the VSO mocking the IDL API as close as possible.
        Either tstart and tend or date_start and date_end or date have
        to be supplied.
        
        Parameters
        ----------
        tstart : datetime.datetime
            Start of the time-range in which records are searched.
        tend : datetime.datetime
            Start of the time-range in which records are searched.
        date : str
            (start date) - (end date)
        start_date : datetime
            the start date
        end_date : datetime
            the end date
        wave : str
            (min) - (max) (unit)
        min_wave : str
            minimum spectral range
        max_wave : str
            maximum spectral range
        unit_wave : str
            spectral range units (Angstrom, GHz, keV)
        extent : str
            VSO 'extent type' ... (FULLDISK, CORONA, LIMB, etc)
        physobj : str
            VSO 'physical observable'
        provider : str
            VSO ID for the data provider (SDAC, NSO, SHA, MSU, etc)
        source : str
            spacecraft or observatory (SOHO, YOHKOH, BBSO, etc)
            synonyms : spacecraft, observatory
        instrument : str
            instrument ID (EIT, SXI-0, SXT, etc)
            synonyms : telescope, inst
        detector : str
            detector ID (C3, EUVI, COR2, etc.)
        layout : str
            layout of the data (image, spectrum, time_series, etc.)

        level : str 
            level of the data product (numeric range, see below)
        pixels : str
            number of pixels (numeric range, see below)
        resolution : str
            effective resolution (1 = full, 0.5 = 2x2 binned, etc)
            numeric range, see below.
        pscale : str
            pixel scale, in arcseconds (numeric range, see below)
        near_time : datetime
            return record closest to the time.  See below.
        sample : int
            attempt to return only one record per SAMPLE seconds.  See below.
        
        Numeric Ranges:
        
            - May be entered as a string or any numeric type for equality matching
            - May be a string of the format '(min) - (max)' for range matching
            - May be a string of the form '(operator) (number)' where operator is one of: lt gt le ge < > <= >=
        
        
        Examples
        --------
        Query all data from eit between 2010-01-01T00:00 and
        2010-01-01T01:00.
        
        >>> qr = client.query_legacy(
        ...     datetime(2010, 1, 1), datetime(2010, 1, 1, 1), instrument='eit')
        
        Returns
        -------
        out : :py:class:`QueryResult` (enhanced list) of matched items. Return value of same type as the one of :py:class:`VSOClient.query`.
        """
        sdk = lambda key: lambda value: {key: value}
        ALIASES = {
            'wave_min': sdk('wave_wavemin'),
            'wave_max': sdk('wave_wavemax'),
            'wave_type': sdk('wave_wavetype'),
            'wave_unit': sdk('wave_waveunit'),
            'min_wave': sdk('wave_wavemin'),
            'max_wave': sdk('wave_wavemax'),
            'type_wave': sdk('wave_wavetype'),
            'unit_wave': sdk('wave_waveunit'),
            'wave': _parse_waverange,
            'inst': sdk('instrument'),
            'telescope': sdk('instrument'),
            'spacecraft': sdk('source'),
            'observatory': sdk('source'),
            'start_date': sdk('time_start'),
            'end_date': sdk('time_end'),
            'start': sdk('time_start'),
            'end': sdk('time_end'),
            'near_time': sdk('time_near'),
            'date': _parse_date,
            'layout': sdk('datatype'),
        }
        kwargs.update({'time_start': tstart, 'time_end': tend})
        
        queryreq = self.api.factory.create('QueryRequest')
        for key, value in kwargs.iteritems():
            if key.startswith('time'):
                value = anytim(value).strftime(TIMEFORMAT)
            for k, v in ALIASES.get(key, sdk(key))(value).iteritems():
                attr = k.split('_')
                lst = attr[-1]
                rest = attr[:-1]
                
                # pylint: disable=E1103
                item = queryreq.block
                for elem in rest:
                    try:
                        item = item[elem]
                    except KeyError:
                        raise ValueError("Unexpected argument %s." % key)
                if lst not in item:
                    raise ValueError("Unexpected argument %s." % key)
                if item[lst]:
                    raise ValueError("Got multiple values for %s." % k)
                item[lst] = v
        try:
            return QueryResponse.create(self.api.service.Query(queryreq))
        except TypeNotFound:
            return QueryResponse([])
    
    def latest(self):
        """ Return newest record (limited to last week). """
        return self.query_legacy(
            datetime.utcnow()  - timedelta(7),
            datetime.utcnow(),
            time_near=datetime.utcnow()
        )
    
    def get(self, query_response, path=None, methods=('URL-FILE',), downloader=None):
        """
        Download data specified in the query_response.
        
        Parameters
        ----------
        query_response : sunpy.net.vso.QueryResponse
            QueryResponse containing the items to be downloaded.
        path : str
            Specify where the data is to be downloaded. Can refer to arbitrary
            fields of the QueryResponseItem (instrument, source, time, ...) via
            string formatting, moreover the file-name of the file downloaded can
            be refered to as file, e.g.
            "{source}/{instrument}/{time.start}/{file}".
        methods : {list of str}
            Methods acceptable to user.
        downloader : sunpy.net.downloader.Downloader
            Downloader used to download the data.
        
        Returns
        -------
        out : :py:class:`Results` object that supplies a list of filenames with meta attributes containing the respective QueryResponse.
        
        Examples
        --------
        >>> res = get(qr).wait()
        """
        if downloader is None:
            downloader = download.Downloader()
            threading.Thread(target=downloader.reactor.run).start()
            res = Results(
                lambda _: downloader.reactor.stop(), 1,
                lambda mp: self.link(query_response, mp)
            )
        else:
            res = Results(
                lambda _: None, 1, lambda mp: self.link(query_response, mp)
            )
        if path is None:
            path = os.path.join(tempfile.mkdtemp(), '{file}')
        fileids = VSOClient.by_fileid(query_response)
        if not fileids:
            res.poke()
            return res
        self.download_all(
            self.api.service.GetData(
                self.make_getdatarequest(query_response, methods)
                ),
            methods, downloader, path,
            fileids, res
        )
        res.poke()
        return res
    
    @staticmethod
    def link(query_response, map_):
        if not map_:
            return []
        ret = []
        
        for record_item in query_response:
            try:
                item = _Str(map_[record_item.fileid]['path'])
            except KeyError:
                continue
            # pylint: disable=W0201
            item.meta = record_item
            ret.append(item)
        return ret
    
    def make_getdatarequest(self, response, methods=None):
        if methods is None:
            methods = self.method_order + ['URL']
        
        return self.create_getdatarequest(
            dict((k, [x.fileid for x in v])
                 for k, v in self.by_provider(response).iteritems()),
            methods
        )
    
    def create_getdatarequest(self, map_, methods, info=None):
        if info is None:
            info = {}
        
        return self.make(
            'VSOGetDataRequest',
            request__method__methodtype=methods, 
            request__info=info,
            request__datacontainer__datarequestitem=[
                self.make('DataRequestItem', provider=k, fileiditem__fileid=[v])
                for k, v in map_.iteritems()
            ]
        )
    
    # pylint: disable=R0913,R0912
    def download_all(self, response, methods, dw, path, qr, res, info=None):
        GET_VERSION = [
            ('0.8', (5, 8)),
            ('0.7', (1, 4)),
            ('0.6', (0, 3)),
        ]
        for dresponse in response.getdataresponseitem:
            for version, (from_, to) in GET_VERSION:
                if getattr(dresponse, version, '0.6') >= version:
                    break
            else:
                res.add_error(UnknownVersion(dresponse))
                continue
            
            # If from_ and to are uninitialized, the else block of the loop
            # continues the outer loop and thus this code is never reached.
            # pylint: disable=W0631
            code = (
                dresponse.status[from_:to]
                if hasattr(dresponse, 'status') else '200'
            )
            if code == '200':
                for dataitem in dresponse.getdataitem.dataitem:
                    try:
                        self.download(
                            dresponse.method.methodtype[0],
                            dataitem.url,
                            dw,
                            res.require(map(str, dataitem.fileiditem.fileid)),
                            res.add_error,
                            path,
                            qr[dataitem.fileiditem.fileid[0]]
                        )
                    except NoData:
                        res.add_error(DownloadFailed(dresponse))
                        continue
                    except Exception:
                        # FIXME: Is this a good idea?
                        res.add_error(DownloadFailed(dresponse))
            elif code == '300' or code == '412' or code == '405':
                if code == '300':
                    try:
                        methods = self.multiple_choices(
                            dresponse.method.methodtype, dresponse
                        )
                    except NoData:
                        res.add_error(MultipleChoices(dresponse))
                        continue
                elif code == '412':
                    try:
                        info = self.missing_information(
                            info, dresponse.info
                        )
                    except NoData:
                        res.add_error(MissingInformation(dresponse))
                        continue
                elif code == '405':
                    try:
                        methods = self.unknown_method(dresponse)
                    except NoData:
                        res.add_error(UnknownMethod(dresponse))
                        continue
                
                files = []
                for dataitem in dresponse.getdataitem.dataitem:
                    files.extend(dataitem.fileiditem.fileid)
                
                request = self.create_getdatarequest(
                    {dresponse.provider: files}, methods, info
                )
                
                self.download_all(
                    self.api.service.GetData(request), methods, dw, path,
                    qr, res, info
                )
            else:
                res.add_error(UnknownStatus(dresponse))
    
    def download(self, method, url, dw, callback, errback, *args):
        """ Override to costumize download action. """
        if method.startswith('URL'):
            return dw.reactor.call_sync(
                partial(dw.download, url, partial(self.mk_filename, *args),
                        callback, errback)
            )
        raise NoData
    
    @staticmethod
    def by_provider(response):
        map_ = defaultdict(list)
        for record in response:
            map_[record.provider].append(record)
        return map_
    
    @staticmethod
    def by_fileid(response):
        return dict(
            (record.fileid, record) for record in response
        )
    
    # pylint: disable=W0613
    def multiple_choices(self, choices, response):
        """ Override to pick between multiple download choices. """
        for elem in self.method_order:
            if elem in choices:
                return [elem]
        raise NoData
    
    # pylint: disable=W0613
    def missing_information(self, info, field):
        """ Override to provide missing information. """
        raise NoData
    
    # pylint: disable=W0613
    def unknown_method(self, response):
        """ Override to pick a new method if the current one is unknown. """
        raise NoData


class InteractiveVSOClient(VSOClient):
    """ Client for use in the REPL. Prompts user for data if required. """
    def multiple_choices(self, choices, response):
        while True:
            for n, elem in enumerate(choices):
                print "(%d) %s" % (n + 1, elem)
            try:
                choice = raw_input("Method number: ")
            except KeyboardInterrupt:
                raise NoData
            if not choice:
                raise NoData
            try:
                choice = int(choice) - 1
            except ValueError:
                continue
            if choice == -1:
                raise NoData
            elif choice >= 0:
                try:
                    return [choices[choice]]
                except IndexError:
                    continue
        
    def missing_information(self, info, field):
        choice = raw_input(field + ': ')
        if not choice:
            raise NoData
        return choice
    
    def search(self, *args, **kwargs):
        """ When passed an Attr object, perform new-style query;
        otherwise, perform legacy query.
        """
        if isinstance(args[0], Attr):
            return self.query(*args)
        else:
            return self.query_legacy(*args, **kwargs)
    
    def get(self, query_response, path=None, methods=('URL-FILE',), downloader=None):
        if path is not None:
            path = os.path.abspath(os.path.expanduser(path))
            if os.path.exists(path) and os.path.isdir(path):
                path = os.path.join(path, '{file}')
        return VSOClient.get(self, query_response, path, methods, downloader)


g_client = None
def search(*args, **kwargs):
    # pylint: disable=W0603
    global g_client
    if g_client is None:
        g_client = InteractiveVSOClient()
    return g_client.search(*args, **kwargs)

search.__doc__ = InteractiveVSOClient.search.__doc__

def get(query_response, path=None, methods=('URL-FILE',), downloader=None):
    # pylint: disable=W0603
    global g_client
    if g_client is None:
        g_client = InteractiveVSOClient()
    return g_client.get(query_response, path, methods, downloader)

get.__doc__ = VSOClient.get.__doc__

if __name__ == "__main__":
    from sunpy.net import vso
    
    client = VSOClient()
    result = client.query(
        vso.attrs.Time((2011, 1, 1), (2011, 1, 1, 10)),
        vso.attrs.Instrument('aia')
    )
    #res = client.get(result, path="/download/path").wait()
