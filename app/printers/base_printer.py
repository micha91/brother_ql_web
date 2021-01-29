from abc import ABC


class BasePrinterWrapper(ABC):
    def print_label(self, context, im, rotate):
        raise NotImplemented

    @property
    def label_type_specs(self):
        raise NotImplemented

    @property
    def label_sizes(self):
        raise NotImplemented

    @property
    def dpi(self):
        raise NotImplemented
