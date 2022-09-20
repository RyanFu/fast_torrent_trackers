import datetime
import logging
import re
import urllib

from jinja2 import Template


def filter_querystring(value, args):
    if value.startswith('?'):
        value = value[1:]
    elif value.find('?') != -1:
        value = value.split('?')[1]
    qs = urllib.parse.parse_qs(value)
    value = qs.get(args)
    if value:
        value = value[0]
    return value


def filter_split(value, args):
    arr = value.split(args[0])
    if args[1] < len(arr):
        return arr[args[1]]
    return None


def filter_re_search(value, args):
    result = re.search(args[0], value)
    if result:
        if args[1] <= len(result.groups()):
            return result.group(args[1])
        else:
            return
    return


def filter_parse_date_elapsed(value, args) -> datetime:
    t = re.match(r'(?:(\d+)日)?(?:(\d+)[時时])?(?:(\d+)分)?', value)
    if not t:
        return None
    now = datetime.datetime.now()
    if t.group(1):
        now = now + datetime.timedelta(days=int(t.group(1)))
    if t.group(2):
        now = now + datetime.timedelta(hours=int(t.group(2)))
    if t.group(3):
        now = now + datetime.timedelta(minutes=int(t.group(3)))
    return now


def filter_parse_date_elapsed_en(value, args):
    if not value:
        return
    value = str(value).strip()
    t = re.match(r'([\d\.]+)\s(seconds|minutes|hours|days|weeks|years)\sago', value)
    if not t:
        return
    now = datetime.datetime.now()
    num = t.group(1)
    unit = t.group(2)
    if unit == 'seconds':
        now = now + datetime.timedelta(seconds=float(num))
    elif unit == 'minutes':
        now = now + datetime.timedelta(minutes=float(num))
    elif unit == 'hours':
        now = now + datetime.timedelta(hours=float(num))
    elif unit == 'days':
        now = now + datetime.timedelta(days=float(num))
    elif unit == 'weeks':
        now = now + datetime.timedelta(weeks=float(num))
    elif unit == 'years':
        now = now + datetime.timedelta(days=float(num) * 365)
    return now


def filter_regexp(value, args):
    return re.sub(args, '', value)


def filter_dateparse(value, args):
    if not value:
        return datetime.datetime.now()
    return datetime.datetime.strptime(value, args)


filter_handler = {
    'lstrip': lambda val, args: str(val).lstrip(str(args[0])),
    'rstrip': lambda val, args: str(val).rstrip(str(args[0])),
    'replace': lambda val, args: val.replace(args[0], args[1]) if val else None,
    'append': lambda val, args: val + args,
    'prepend': lambda val, args: args + val,
    'tolower': lambda val, args: val.lower(),
    'toupper': lambda val, args: val.upper(),
    'split': filter_split,
    'dateparse': filter_dateparse,
    'querystring': filter_querystring,
    're_search': filter_re_search,
    'date_elapsed_parse': filter_parse_date_elapsed,
    'date_en_elapsed_parse': filter_parse_date_elapsed_en,
    'regexp': filter_regexp
}


class HtmlParser:
    @staticmethod
    def __select_value(tag, rule):
        val = None
        if tag:
            if 'attribute' in rule:
                if tag.has_attr(rule['attribute']):
                    attr = tag.attrs[rule['attribute']]
                    if isinstance(attr, list):
                        val = attr[0]
                    else:
                        val = attr
            elif 'method' in rule:
                if rule['method'] == 'next_sibling' and tag and tag.next_sibling:
                    val = tag.next_sibling.text
            elif 'remove' in rule:
                remove_tag_name = rule['remove'].split(',')
                for rt in remove_tag_name:
                    s = tag.select(rt)
                    if not s:
                        continue
                    for i in s:
                        i.extract()
                val = tag.text
            elif 'contents' in rule:
                idx = rule['contents']
                val = tag.contents[idx].text
            else:
                val = tag.text
        if val:
            val = val.strip()
        return val

    @staticmethod
    def __case_value(r, case):
        val = None
        for ck in case:
            if ck == '*':
                val = case[ck]
                break
            if r.select_one(ck):
                val = case[ck]
                break
        return val

    @staticmethod
    def __filter_value(value, filters):
        if not value:
            return value
        for f in filters:
            if f['name'] in filter_handler:
                value = filter_handler[f['name']](value, f.get('args'))
        return value

    @staticmethod
    def parse_item_fields(item_tag, item_rule, context=None):
        if not item_tag:
            return {}
        self = HtmlParser
        values = {}
        for key in item_rule:
            rule = item_rule[key]
            val = None
            try:
                if 'text' in rule:
                    if isinstance(rule['text'], str) and rule['text'].find('{') != -1:
                        tmpl = Template(rule['text'])
                        ctx = {'fields': values, 'now': datetime.datetime.now()}
                        if context:
                            ctx.update(context)
                        val = tmpl.render(ctx)
                    else:
                        val = rule.get('text')
                elif 'selector' in rule:
                    val = self.__select_value(item_tag.select_one(rule['selector']), rule)
                elif 'selectors' in rule:
                    tag_list = item_tag.select(rule['selectors'])
                    if rule.get('index'):
                        if tag_list and rule['index'] < len(tag_list):
                            tag = tag_list[rule['index']]
                            val = self.__select_value(tag, rule)
                    else:
                        val = []
                        for t in tag_list:
                            val.append(self.__select_value(t, rule))
                elif 'case' in rule:
                    val = self.__case_value(item_tag, rule['case'])
                if 'filters' in rule:
                    val = self.__filter_value(val, rule['filters'])
                if (val is None or val == '') and 'default_value' in rule:
                    if isinstance(rule['default_value'], str) and rule['default_value'].find('{{') != -1:
                        tmpl = Template(rule['default_value'])
                        ctx = {'fields': values, 'now': datetime.datetime.now(), 'max_time': datetime.datetime.max}
                        if context:
                            ctx.update(context)
                        val = tmpl.render(ctx)
                    else:
                        val = rule['default_value']
                    if val and 'default_value_format' in rule:
                        val = datetime.datetime.strptime(val, rule['default_value_format'])
            except Exception as e:
                logging.error('%s解析出错 values: %s tag: %s' % (key, values, item_tag), exc_info=True)
                continue
            values[key] = val
        return values
