import logging
from brother_ql.labels import FormFactor, Color
from app.printers.base_printer import BasePrinterWrapper
from brother_label_printer import backends, label
from brother_label_printer.printers.brother_pt700 import P700

logger = logging.getLogger(__name__)
models = ['PT-P700']


class ImgWrapper:
    def render(self, img):
        return img


class PictureLabel(label.Label):
    items = [[
        ImgWrapper()
    ]]


class PrinterWrapperPT(BasePrinterWrapper):
    def __init__(self, parser):
        self.backend_class = backends.PyUSBBackend.auto()

    def print_label(self, context, im, rotate):
        return_dict = dict()
        try:
            printer = P700(self.backend_class)
            printer.print_label(PictureLabel(im), context['print_count'])
        except Exception as e:
            return_dict['message'] = str(e)
            logger.warning('Exception happened: %s', e)
            return return_dict
        return_dict['success'] = True
        return return_dict

    @property
    def label_sizes(self):
        return ['3.5', '6', '9', '12', '18', '24']

    @property
    def label_type_specs(self):
        ret = dict()
        for width in self.label_sizes:
            ret[width] = {
                'name': width + 'mm endless',
                'kind': FormFactor.ENDLESS,
                'color': Color.BLACK_WHITE,
                'tape_size': (float(width), 0),
                'dots_printable': (int(P700.DPI[0] * float(width) / 25.4), 0)
            }
        return ret

    @property
    def dpi(self):
        return P700.DPI[0]
