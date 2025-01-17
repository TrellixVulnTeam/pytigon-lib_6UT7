#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
The module enables the dynamic creation of documents in a odf format (https://en.wikipedia.org/wiki/OpenDocument).
Process of documents creation begins with the creation of the template. It is also in odf format.
Template is a normal static document supplemented with dynamic structures placed in comments to the selected cells.
The syntax of these additional comments is consistent with django. There are additional syntax elements
to control the place where dynamic structures are activated.

Additional syntax:
    First char in spreadsheet cell:
        * - result in text format
        : - result as number
        @ or $ - result as formula
    First char in note:
        !   - move expression to current cell
              element before cell and element after cell separated by char: '@'
              example:
              !{% for i in list %}@{%endfor%}
        !!  - move expression to current row
        !!! - move expression to current sheet
        
    Syntax compatibile with django:
        {{var}}, {% block %} etc.
    There are aliases: '_start_' is alias for '{{'
                       '_end_' is alias for '}}'
"""

import os.path
import io
from zipfile import ZipFile
import xml.dom.minidom

from django.template import Template
from django.http import HttpResponse
from django.conf import settings
from django.template.exceptions import TemplateDoesNotExist

from pytigon_lib.schfs.vfstools import get_temp_filename
from pytigon_lib.schspreadsheet.odf_process import OdfDocTransform
from pytigon_lib.schspreadsheet.ooxml_process import OOXmlDocTransform

template_dirs = getattr(settings, "TEMPLATES")[0]["DIRS"]


class OdfDocTemplateTransform(OdfDocTransform):
    def process_template(self, doc_str, context):
        return Template(
            "{% load exsyntax %}{% load exfiltry %}{% load expr %}" + doc_str
        ).render(context)


class OOXmlDocTemplateTransform(OOXmlDocTransform):
    def process_template(self, doc_str, context):
        return Template(
            "{% load exsyntax %}{% load exfiltry %}{% load expr %}" + doc_str
        ).render(context)


def oo_dict(template_name):
    z = ZipFile(template_dirs[0] + "/" + template_name, "r")
    doc_content = z.read("content.xml")
    z.close()
    doc = xml.dom.minidom.parseString(doc_content.replace("&apos;", "'"))
    elementy = doc.getElementsByTagName("table:table")
    ret = []
    for element in elementy:
        element.getAttribute("table:name")
        ret.append(
            (element.getAttribute("table:name"), element.getAttribute("table:name"))
        )
    return ret


class DefaultTbl(object):
    def __init__(self):
        self.row = -1
        self.col = -1

    def IncRow(self, row=1):
        self.row = self.row + row
        return ""

    def IncCol(self, col=1):
        self.col = self.col + col
        return ""

    def SetCol(self, col):
        self.col = col
        return ""

    def SetRow(self, row):
        self.row = row
        return ""


def _render_doc(doc_type, template_name, context_instance=None, debug=None):
    """Render odf file content, save rendered file and return its name

    Args:
        template_name - name of template. Template is odf file with special syntax.
        context_instance - see django.template.Context
        debug - if True - print some additional information to console

    Returns:
        (output_file_name, template_name)
        output_file_name is the name of temporary file with rendered content
        template_name - real path to template odf file
    """
    if not "tbl" in context_instance:
        context = {
            "tbl": DefaultTbl(),
        }
    else:
        context = {}

    ret2 = None

    with context_instance.push(context):
        if not "tbl" in context_instance:
            context_instance["tbl"] = DefaultTbl()

        if template_name.__class__ in (list, tuple):
            test = False
            for tname in template_name:
                if tname[0] == "/":
                    name = tname
                    if os.path.exists(name):
                        test = True
                        break
                else:
                    for template_dir in template_dirs:
                        name = template_dir + "/" + tname
                        if os.path.exists(name):
                            test = True
                            break
                    if test:
                        break
            if not test:
                raise TemplateDoesNotExist(";".join(template_name))
        else:
            name = template_name
        name_out = get_temp_filename()
        if doc_type.lower().startswith("od"):
            doc = OdfDocTemplateTransform(name, name_out)
        else:
            doc = OOXmlDocTemplateTransform(name, name_out)

        ret = doc.process(context_instance, debug)

        if ret != 1:
            ret2 = (None, name)
            os.remove(name_out)
        else:
            ret2 = (name_out, name)
    return ret2


def _render_doc_to_response(
    doc_type, doc_content_type, template_name, context_instance=None, debug=None
):

    s = _render_doc(doc_type, template_name, context_instance, debug)

    if not s[0]:
        response = None
    else:
        if "_" in s[1]:
            name = s[1].split("_")[1]
        else:
            name = s[1]
        response = HttpResponse()
        response["Content-Disposition"] = "attachment; filename=%s" % name
        response["Content-Type"] = "application/vnd.oasis.opendocument.spreadsheet"
        f = open(s[0], "rb")
        response.content = f.read()
        f.close()
        os.remove(s[0])
    return response


def render_odf(template_name, context_instance=None, debug=None):
    return _render_doc("ODF", template_name, context_instance, debug)


def render_ooxml(template_name, context_instance=None, debug=None):
    return _render_doc("OOXML", template_name, context_instance, debug)


def render_to_response_odf(template_name, context_instance=None, debug=None):
    """Render odf file content, save it to HttpResponse (see django.http.HttpResponse)

    Args:
        template_name - name of template. Template is odf file with special syntax.
        context_instance - see django.template.Context
        debug - if True - print some additional information to console

    Returns:
        HttpResponse object
    """
    return _render_doc_to_response(
        "ODF",
        "application/vnd.oasis.opendocument.spreadsheet",
        template_name,
        context_instance,
        debug,
    )


def render_to_response_ooxml(template_name, context_instance=None, debug=None):
    """Render odf file content, save it to HttpResponse (see django.http.HttpResponse)

    Args:
        template_name - name of template. Template is ooxml file with special syntax.
        context_instance - see django.template.Context
        debug - if True - print some additional information to console

    Returns:
        HttpResponse object
    """
    return _render_doc_to_response(
        "OOXML",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        template_name,
        context_instance,
        debug,
    )
