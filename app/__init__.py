#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This is a web service to print labels on Brother QL label printers.
"""

import sys
import logging
import random
import argparse
import qrcode
import os
from brother_ql.devicedependent import ENDLESS_LABEL, DIE_CUT_LABEL, ROUND_DIE_CUT_LABEL

from flask import Flask, render_template, request, make_response, redirect, url_for
from flask_bootstrap import Bootstrap
from PIL import Image, ImageDraw, ImageFont

from . import fonts
from app.utils import convert_image_to_bw, pdffile_to_image, imgfile_to_image, image_to_png_bytes
from . import settings
from .printers.base_printer import BasePrinterWrapper
from .printers.brother_ptouch import PrinterWrapperPT
from .printers.brother_ql import PrinterWrapperQL

app = Flask(__name__)

logger = logging.getLogger(__name__)

LINE_SPACINGS = (100, 150, 200, 250, 300)

# Don't change as brother_ql is using this DPI value
LABEL_SIZES = []

PRINTER: BasePrinterWrapper

FONTS: fonts.Fonts


@app.route('/')
def index():
    return redirect(url_for('labeldesigner'))


@app.route('/labeldesigner')
def labeldesigner():
    return render_template('labeldesigner.jinja2',
                           font_family_names=FONTS.fontlist(),
                           label_sizes=LABEL_SIZES,
                           website=settings.CONFIG['WEBSITE'],
                           label=settings.CONFIG['LABEL'],
                           default_orientation=settings.CONFIG['LABEL']['DEFAULT_ORIENTATION'],
                           default_qr_size=settings.CONFIG['LABEL']['DEFAULT_QR_SIZE'],
                           line_spacings=LINE_SPACINGS,
                           default_line_spacing=settings.CONFIG['LABEL']['DEFAULT_LINE_SPACING'],
                           default_dpi=PRINTER.dpi,
                           available_orientations=settings.CONFIG['LABEL']['AVAILABLE_ORIENTATION'],
                           )


def get_label_context(request):
    """ might raise LookupError() """

    d = request.values  # UTF-8 decoded form data

    context = {
        'text': d.get('text', None),
        'qr_data': d.get('qr_data', d.get('text', "")),
        'font_size': int(d.get('font_size', 100)),
        'font_family': d.get('font_family'),
        'font_style': d.get('font_style'),
        'label_size': d.get('label_size', settings.CONFIG['LABEL']['DEFAULT_SIZE']),
        'kind': PRINTER.label_type_specs[str(d.get('label_size', settings.CONFIG['LABEL']['DEFAULT_SIZE']))]['kind'],
        'margin': int(d.get('margin', 10)),
        'threshold': int(d.get('threshold', 70)),
        'align': d.get('align', 'center'),
        'orientation': d.get('orientation', 'standard'),
        'margin_top': float(d.get('margin_top', 24)) / 100.,
        'margin_bottom': float(d.get('margin_bottom', 45)) / 100.,
        'margin_left': float(d.get('margin_left', 35)) / 100.,
        'margin_right': float(d.get('margin_right', 35)) / 100.,
        'print_type': d.get('print_type', 'text'),
        'qrcode_size': int(d.get('qrcode_size', 10)),
        'qrcode_correction': d.get('qrcode_correction', 'L'),
        'print_count': int(d.get('print_count', 1)),
        'print_color': d.get('print_color', 'black'),
        'line_spacing': int(d.get('line_spacing', 100)),
        'cut_once': int(d.get('cut_once', 0)),
    }
    context['margin_top'] = int(context['font_size'] * context['margin_top'])
    context['margin_bottom'] = int(context['font_size'] * context['margin_bottom'])
    context['margin_left'] = int(context['font_size'] * context['margin_left'])
    context['margin_right'] = int(context['font_size'] * context['margin_right'])

    context['fill_color'] = (255, 0, 0) if 'red' in context['label_size'] and context['print_color'] == 'red' else (
    0, 0, 0)

    context['cut_once'] = True if context['cut_once'] == 1 else False

    qrSwitch = {
        'L': qrcode.constants.ERROR_CORRECT_L,
        'M': qrcode.constants.ERROR_CORRECT_M,
        'Q': qrcode.constants.ERROR_CORRECT_Q,
        'H': qrcode.constants.ERROR_CORRECT_H
    }
    context['qrcode_correction'] = qrSwitch.get(context['qrcode_correction'], qrcode.constants.ERROR_CORRECT_L)

    def get_uploaded_image(image):
        try:
            name, ext = os.path.splitext(image.filename)
            if ext.lower() in ('.png', '.jpg', '.jpeg'):
                image = imgfile_to_image(image)
                return convert_image_to_bw(image, 200)
            elif ext.lower() in ('.pdf'):
                image = pdffile_to_image(image, PRINTER.dpi)
                return convert_image_to_bw(image, 200)
            else:
                return None
        except AttributeError:
            return None

    context['upload_image'] = get_uploaded_image(request.files.get('image', None))

    def get_font_path(font_family_name, font_style_name):
        try:
            if font_family_name is None or font_style_name is None:
                font_family_name = settings.CONFIG['LABEL']['DEFAULT_FONT']['family']
                font_style_name = settings.CONFIG['LABEL']['DEFAULT_FONT']['style']
            font_path = FONTS.fonts[font_family_name][font_style_name]
        except KeyError:
            raise LookupError("Couln't find the font & style")
        return font_path

    context['font_path'] = get_font_path(context['font_family'], context['font_style'])

    def get_label_dimensions(label_size):
        try:
            ls = PRINTER.label_type_specs[context['label_size']]
        except KeyError:
            raise LookupError("Unknown label_size")
        return ls['dots_printable']

    width, height = get_label_dimensions(context['label_size'])
    if height > width:
        width, height = height, width
    if context['orientation'] == 'rotated':
        height, width = width, height
    context['width'], context['height'] = width, height

    return context


def create_qr_code(text, size, correction, fill_color):
    qr = qrcode.QRCode(
        version=1,
        error_correction=correction,
        box_size=size,
        border=0,
    )
    qr.add_data(text)
    qr.make(fit=True)
    qr_img = qr.make_image(
        fill_color='red' if (255, 0, 0) == fill_color else 'black',
        back_color="white")
    return qr_img


def create_label_im(text, **kwargs):
    if kwargs['print_type'] == 'qrcode' or kwargs['print_type'] == 'qrcode_text':
        print(kwargs)
        img = create_qr_code(
            kwargs['qr_data'],
            kwargs['qrcode_size'],
            kwargs['qrcode_correction'],
            kwargs['fill_color']
        )
    elif kwargs['print_type'] == 'image':
        img = kwargs['upload_image']
    else:
        img = None

    if kwargs['print_type'] == 'qrcode':
        return assemble_label_im(text, img, False, **kwargs)
    elif kwargs['print_type'] == 'qrcode_text':
        return assemble_label_im(text, img, True, **kwargs)
    elif kwargs['print_type'] == 'image':
        return assemble_label_im(text, img, False, **kwargs)
    else:
        return assemble_label_im(text, None, True, **kwargs)


def assemble_label_im(text, image, include_text, **kwargs):
    if image is not None:
        image_width, image_height = image.size
    else:
        image_width, image_height = (0, 0)

    label_type = kwargs['kind']

    if include_text:
        im_font = ImageFont.truetype(kwargs['font_path'], kwargs['font_size'])
        im = Image.new('L', (20, 20), 'white')
        draw = ImageDraw.Draw(im)
        # workaround for a bug in multiline_textsize()
        # when there are empty lines in the text:
        lines = []
        for line in text.split('\n'):
            if line == '':
                line = ' '
            lines.append(line)
        text = '\n'.join(lines)
        textsize = draw.multiline_textsize(text, font=im_font,
                                           spacing=int(kwargs['font_size'] * ((kwargs['line_spacing'] - 100) / 100)))
    else:
        textsize = (0, 0)

    width, height = kwargs['width'], kwargs['height']
    if kwargs['orientation'] == 'standard':
        if label_type in (ENDLESS_LABEL,):
            height = image_height + textsize[1] + kwargs['margin_top'] + kwargs['margin_bottom']
    elif kwargs['orientation'] == 'rotated':
        if label_type in (ENDLESS_LABEL,):
            width = image_width + textsize[0] + kwargs['margin_left'] + kwargs['margin_right']

    if kwargs['orientation'] == 'standard':
        if label_type in (DIE_CUT_LABEL, ROUND_DIE_CUT_LABEL):
            vertical_offset = (height - image_height - textsize[1]) // 2
            vertical_offset += (kwargs['margin_top'] - kwargs['margin_bottom']) // 2
        else:
            vertical_offset = kwargs['margin_top']

        vertical_offset += image_height
        horizontal_offset = max((width - textsize[0]) // 2, 0)
        horizontal_offset_image = (width - image_width) // 2
        vertical_offset_image = kwargs['margin_top']

    elif kwargs['orientation'] == 'rotated':
        vertical_offset = (height - textsize[1]) // 2
        vertical_offset += (kwargs['margin_top'] - kwargs['margin_bottom']) // 2
        if label_type in (DIE_CUT_LABEL, ROUND_DIE_CUT_LABEL):
            horizontal_offset = max((width - image_width - textsize[0]) // 2, 0)
        else:
            horizontal_offset = kwargs['margin_left']
        horizontal_offset += image_width
        horizontal_offset_image = kwargs['margin_left']
        vertical_offset_image = (height - image_height) // 2

    else:
        raise ValueError("orientation was not defined correctly.")

    offset = horizontal_offset, vertical_offset
    image_offset = horizontal_offset_image, vertical_offset_image

    im = Image.new('RGB', (width, height), 'white')

    if image is not None:
        im.paste(image, image_offset)

    if include_text:
        draw = ImageDraw.Draw(im)
        draw.multiline_text(
            offset,
            text,
            kwargs['fill_color'],
            font=im_font,
            align=kwargs['align'],
            spacing=int(kwargs['font_size'] * ((kwargs['line_spacing'] - 100) / 100)))

    return im


@app.route('/api/font/styles', methods=['POST', 'GET'])
def get_font_styles():
    font = request.values.get('font', settings.CONFIG['LABEL']['DEFAULT_FONT']['family'])
    return FONTS.fonts[font]


@app.route('/api/preview', methods=['POST', 'GET'])
def get_preview_from_image():
    context = get_label_context(request)
    im = create_label_im(**context)

    return_format = request.values.get('return_format', 'png')

    if return_format == 'base64':
        import base64
        response = make_response(base64.b64encode(image_to_png_bytes(im)))
        response.headers.set('Content-type', 'text/plain')
        return response
    else:
        response = make_response(image_to_png_bytes(im))
        response.headers.set('Content-type', 'image/png')
        return response


@app.route('/api/print', methods=['POST', 'GET'])
def print_text():
    """
    API to print a label

    returns: JSON

    Ideas for additional URL parameters:
    - alignment
    """

    return_dict = {'success': False}

    try:
        context = get_label_context(request)
    except LookupError as e:
        return_dict['error'] = str(e)
        return return_dict

    if context['text'] is None:
        return_dict['error'] = 'Please provide the text for the label'
        return return_dict

    im = create_label_im(**context)
    if settings.DEBUG:
        im.save('sample-out.png')

    if context['kind'] == ENDLESS_LABEL:
        rotate = 0 if context['orientation'] == 'standard' else 90
    elif context['kind'] in (ROUND_DIE_CUT_LABEL, DIE_CUT_LABEL):
        rotate = 'auto'
    else:
        return_dict['error'] = 'Unknown label type.'
        return return_dict

    print_result = PRINTER.print_label(context, im, rotate)

    for key, val in print_result.items():
        return_dict[key] = val
    return return_dict


def main():
    global FONTS, LABEL_SIZES, PRINTER
    parser = argparse.ArgumentParser(description=__doc__)
    from brother_ql.devicedependent import models as ql_models
    from .printers.brother_ptouch import models as pt_models
    model_list = ql_models + pt_models
    parser.add_argument('--port', default=False)
    parser.add_argument(
        '--loglevel', type=lambda x: getattr(logging, x.upper()), default=False)
    parser.add_argument('--font-folder', default=False,
                        help='folder for additional .ttf/.otf fonts')
    parser.add_argument('--default-label-size', default=False,
                        help='Label size inserted in your printer. Defaults to 62.')
    parser.add_argument('--default-orientation', default=False, choices=('standard', 'rotated'),
                        help='Label orientation, defaults to "standard". To turn your text by 90°, state "rotated".')
    parser.add_argument('--model', default=False, choices=model_list,
                        help='The model of your printer (default: QL-500)')
    parser.add_argument('printer', nargs='?', default=False,
                        help='String descriptor for the printer to use (like tcp://192.168.0.23:9100 or file:///dev/usb/lp0)')
    args = parser.parse_args()

    settings.init()

    if args.printer:
        settings.CONFIG['PRINTER']['PRINTER'] = args.printer

    if args.port:
        PORT = args.port
    else:
        PORT = settings.CONFIG['SERVER']['PORT']

    if args.loglevel:
        LOGLEVEL = args.loglevel
    else:
        LOGLEVEL = settings.CONFIG['SERVER']['LOGLEVEL']

    if LOGLEVEL == 'DEBUG':
        settings.DEBUG = True
    else:
        settings.DEBUG = False

    if args.model:
        settings.CONFIG['PRINTER']['MODEL'] = args.model

    if args.default_label_size:
        settings.CONFIG['LABEL']['DEFAULT_SIZE'] = args.default_label_size

    if args.default_orientation:
        settings.CONFIG['LABEL']['DEFAULT_ORIENTATION'] = args.default_orientation

    if args.font_folder:
        ADDITIONAL_FONT_FOLDER = args.font_folder
    else:
        ADDITIONAL_FONT_FOLDER = settings.CONFIG['SERVER']['ADDITIONAL_FONT_FOLDER']

    logging.basicConfig(level=LOGLEVEL)

    if settings.CONFIG['PRINTER']['MODEL'] in pt_models:
        PRINTER = PrinterWrapperPT(parser)
        settings.CONFIG['LABEL']['DEFAULT_ORIENTATION'] = 'rotated'
        settings.CONFIG['LABEL']['AVAILABLE_ORIENTATION'] = ['rotated']

    else:
        PRINTER = PrinterWrapperQL(parser)
        settings.CONFIG['LABEL']['AVAILABLE_ORIENTATION'] = ['rotated', 'standard']

    if settings.CONFIG['LABEL']['DEFAULT_SIZE'] not in PRINTER.label_sizes:
        parser.error("Invalid --default-label-size. Please choose on of the following:\n:" + " ".join(PRINTER.label_sizes))

    FONTS = fonts.Fonts()
    FONTS.scan_global_fonts()
    if ADDITIONAL_FONT_FOLDER:
        FONTS.scan_fonts_folder(ADDITIONAL_FONT_FOLDER)

    LABEL_SIZES = [(
        name,
        PRINTER.label_type_specs[name]['name'],
        (PRINTER.label_type_specs[name]['kind'] in (
            ROUND_DIE_CUT_LABEL,))  # True if round label
    ) for name in PRINTER.label_sizes]

    if not FONTS.fonts_available():
        sys.stderr.write(
            "Not a single font was found on your system. Please install some or use the \"--font-folder\" argument.\n")
        sys.exit(2)

    for font in settings.CONFIG['LABEL']['DEFAULT_FONTS']:
        if font['family'] in FONTS.fonts.keys() and font['style'] in FONTS.fonts[font['family']].keys():
            settings.CONFIG['LABEL']['DEFAULT_FONT'] = font
            logger.debug("Selected the following default font: {}".format(font))
            break
        else:
            pass
    if settings.CONFIG['LABEL'].get('DEFAULT_FONT', None) is None:
        sys.stderr.write('Could not find any of the default fonts. Choosing a random one.\n')
        family = random.choice(list(FONTS.fonts.keys()))
        style = random.choice(list(FONTS.fonts[family].keys()))
        settings.CONFIG['LABEL']['DEFAULT_FONT'] = {'family': family, 'style': style}
        sys.stderr.write('The default font is now set to: {family} ({style})\n'.format(
            **settings.CONFIG['LABEL']['DEFAULT_FONT']))

    # initialize bootstrap
    app.config['BOOTSTRAP_SERVE_LOCAL'] = True
    bootstrap = Bootstrap(app)

    print(settings.CONFIG)
    print(settings.DEBUG)

    app.run(host=settings.CONFIG['SERVER']['HOST'], port=PORT, debug=True)
