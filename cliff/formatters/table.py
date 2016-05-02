"""Output formatters using prettytable.
"""

import prettytable
import six

from cliff import utils
from .base import ListFormatter, SingleFormatter


class TableFormatter(ListFormatter, SingleFormatter):

    ALIGNMENTS = {
        int: 'r',
        str: 'l',
        float: 'r',
    }
    try:
        ALIGNMENTS[unicode] = 'l'
    except NameError:
        pass

    def add_argument_group(self, parser):
        group = parser.add_argument_group('table formatter')
        group.add_argument(
            '--max-width',
            metavar='<integer>',
            default=0,
            type=int,
            help='Maximum display width, 0 to disable',
        )

    def emit_list(self, column_names, data, stdout, parsed_args):
        x = prettytable.PrettyTable(
            column_names,
            print_empty=False,
        )
        x.padding_width = 1
        # Figure out the types of the columns in the
        # first row and set the alignment of the
        # output accordingly.
        data_iter = iter(data)
        try:
            first_row = next(data_iter)
        except StopIteration:
            pass
        else:
            for value, name in zip(first_row, column_names):
                alignment = self.ALIGNMENTS.get(type(value), 'l')
                x.align[name] = alignment
            # Now iterate over the data and add the rows.
            x.add_row(first_row)
            for row in data_iter:
                row = [r.replace('\r\n', '\n').replace('\r', ' ')
                       if isinstance(r, six.string_types) else r
                       for r in row]
                x.add_row(row)

        # Choose a reasonable min_width to better handle many columns on a
        # narrow console. The table will overflow the console width in
        # preference to wrapping columns smaller than 8 characters.
        min_width = 8
        self._assign_max_widths(
            stdout, x, int(parsed_args.max_width), min_width)

        formatted = x.get_string()
        stdout.write(formatted)
        stdout.write('\n')
        return

    def emit_one(self, column_names, data, stdout, parsed_args):
        x = prettytable.PrettyTable(field_names=('Field', 'Value'),
                                    print_empty=False)
        x.padding_width = 1
        # Align all columns left because the values are
        # not all the same type.
        x.align['Field'] = 'l'
        x.align['Value'] = 'l'
        for name, value in zip(column_names, data):
            value = (value.replace('\r\n', '\n').replace('\r', ' ') if
                     isinstance(value, six.string_types) else value)
            x.add_row((name, value))

        # Choose a reasonable min_width to better handle a narrow
        # console. The table will overflow the console width in preference
        # to wrapping columns smaller than 16 characters in an attempt to keep
        # the Field column readable.
        min_width = 16
        self._assign_max_widths(
            stdout, x, int(parsed_args.max_width), min_width)

        formatted = x.get_string()
        stdout.write(formatted)
        stdout.write('\n')
        return

    @staticmethod
    def _field_widths(field_names, first_line):

        # use the first line +----+-------+ to infer column widths
        # accounting for padding and dividers
        widths = [max(0, len(i) - 2) for i in first_line.split('+')[1:-1]]
        return dict(zip(field_names, widths))

    @staticmethod
    def _width_info(term_width, field_count):
        # remove padding and dividers for width available to actual content
        usable_total_width = max(0, term_width - 1 - 3 * field_count)

        # calculate width per column if all columns were equal
        if field_count == 0:
            optimal_width = 0
        else:
            optimal_width = max(0, usable_total_width // field_count)

        return usable_total_width, optimal_width

    @staticmethod
    def _build_shrink_fields(usable_total_width, optimal_width,
                             field_widths, field_names):
        shrink_fields = []
        shrink_remaining = usable_total_width
        for field in field_names:
            w = field_widths[field]
            if w <= optimal_width:
                # leave alone columns which are smaller than the optimal width
                shrink_remaining -= w
            else:
                shrink_fields.append(field)

        return shrink_fields, shrink_remaining

    @staticmethod
    def _plan_shrink(shrink_fields, shrink_remaining):
        sorted_widths = sorted([len(field) for field in shrink_fields])
        shrink_remaining -= sum(sorted_widths)
        if shrink_remaining <= 0:
            return {field: 0 for field in shrink_fields}

        sorted_widths.append(shrink_remaining)
        target_width = 0
        for pos, current_width in enumerate(sorted_widths):
            if pos * (current_width - target_width) < shrink_remaining:
                shrink_remaining -= pos * (current_width - target_width)
                target_width = current_width
            else:
                target_width += shrink_remaining // pos
                modulo = shrink_remaining % pos
                break

        shrink_plan = {}
        for field in shrink_fields:
            width = len(field)
            if width <= target_width:
                width = target_width + (1 if modulo > 0 else 0)
                modulo -= 1
            shrink_plan[field] = width
        return shrink_plan

    @staticmethod
    def _assign_max_widths(stdout, x, max_width, min_width=0):
        if min_width:
            x.min_width = min_width

        if max_width > 0:
            x.max_width = max_width
            return

        term_width = utils.terminal_width(stdout)
        if not term_width:
            # not a tty, so do not set any max widths
            return
        field_count = len(x.field_names)

        try:
            first_line = x.get_string().splitlines()[0]
            if len(first_line) <= term_width:
                return
        except IndexError:
            return

        usable_total_width, optimal_width = TableFormatter._width_info(
            term_width, field_count)

        field_widths = TableFormatter._field_widths(x.field_names, first_line)

        shrink_fields, shrink_remaining = TableFormatter._build_shrink_fields(
            usable_total_width, optimal_width, field_widths, x.field_names)

        shrink_plan = TableFormatter._plan_shrink(
            shrink_fields, shrink_remaining)

        for field, shrink_to in shrink_plan.iteritems():
            x.max_width[field] = max(min_width, shrink_to)
