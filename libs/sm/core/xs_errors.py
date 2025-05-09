# Copyright (C) Citrix Systems Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation; version 2.1 only.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
#
# Xensource error codes
#

import errno
import os
import xml.dom.minidom
import xmlrpc.client

XML_DEFS = '/usr/share/sm/XE_SR_ERRORCODES.xml'


class SRException(Exception):
    """Exception raised by storage repository operations"""
    errno = errno.EINVAL

    def __init__(self, reason):
        super().__init__(reason)

    def toxml(self):
        return xmlrpc.client.dumps(xmlrpc.client.Fault(
            int(self.errno), str(self)), "", True)


class SROSError(SRException):
    """Class which looks valuely like OSError"""

    def __init__(self, errno, reason):
        self.errno = errno
        self.reason = reason
        super().__init__(reason)

    def message(self):
        return self.reason

class XenError(Exception):
    def __new__(self, key, opterr=None):
        # Check the XML definition file exists
        if not os.path.exists(XML_DEFS):
            raise Exception(f"No XML def file found ({XML_DEFS})")

        # Read the definition list
        errorlist = self._fromxml('SM-errorcodes')

        # ########DEBUG#######
        #for val in self.errorlist.keys():
        #    subdict = self.errorlist[val]
        #    print "KEY [%s]" % val
        #    for subval in subdict.keys():
        #        print "\tSUBKEY: %s, VALUE: %s" % (subval,subdict[subval])
        ########END#######

        # Now find the specific error
        if key in errorlist:
            subdict = errorlist[key]
            errorcode = int(subdict['value'])
            errormessage = subdict['description']
            if opterr is not None:
                errormessage += " [opterr=%s]" % opterr
            return SROSError(errorcode, errormessage)

        # development error
        return SROSError(1, "Error reporting error, unknown key %s" % key)

    @staticmethod
    def _fromxml(tag):
        dom = xml.dom.minidom.parse(XML_DEFS)
        objectlist = dom.getElementsByTagName(tag)[0]

        errorlist = {}
        for node in objectlist.childNodes:
            taglist = {}
            newval = False
            for n in node.childNodes:
                if n.nodeType == n.ELEMENT_NODE and node.nodeName == 'code':
                    taglist[n.nodeName] = ""
                    for e in n.childNodes:
                        if e.nodeType == e.TEXT_NODE:
                            newval = True
                            taglist[n.nodeName] += e.data
            if newval:
                name = taglist['name']
                errorlist[name] = taglist
        return errorlist
