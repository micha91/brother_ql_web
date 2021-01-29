import logging

from brother_ql.devicedependent import label_type_specs, label_sizes
from brother_ql import BrotherQLRaster, create_label
from brother_ql.backends import backend_factory, guess_backend

from app import settings
from app.printers.base_printer import BasePrinterWrapper

logger = logging.getLogger(__name__)


class PrinterWrapperQL(BasePrinterWrapper):
    def __init__(self, parser):
        try:
            selected_backend = guess_backend(settings.CONFIG['PRINTER']['PRINTER'])
        except ValueError:
            parser.error("Couln't guess the backend to use from the printer string descriptor")
            raise
        self.backend_class = backend_factory(selected_backend)['backend_class']

    def print_label(self, context, im, rotate):
        return_dict = dict()
        qlr = BrotherQLRaster(settings.CONFIG['PRINTER']['MODEL'])
        red = False
        if 'red' in context['label_size']:
            red = True
        for cnt in range(1, context['print_count'] + 1):
            if not context['cut_once']:
                cut = True
            elif context['cut_once'] and cnt == context['print_count']:
                cut = True
            else:
                cut = False

            create_label(
                qlr,
                im,
                context['label_size'],
                red=red,
                threshold=context['threshold'],
                cut=cut,
                rotate=rotate)
        if not settings.DEBUG:
            try:
                be = self.backend_class(settings.CONFIG['PRINTER']['PRINTER'])
                be.write(qlr.data)
                be.dispose()
                del be
            except Exception as e:
                return_dict['message'] = str(e)
                logger.warning('Exception happened: %s', e)
                return return_dict
        return_dict['success'] = True
        if settings.DEBUG:
            return_dict['data'] = str(qlr.data)
        return return_dict

    @property
    def label_sizes(self):
        return label_sizes

    @property
    def label_type_specs(self):
        return label_type_specs

    @property
    def dpi(self):
        return 300
