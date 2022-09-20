from jinja2 import Template


def render_text(text, **context):
    """
    把模版语法渲染成最终字符串
    :param text:
    :param context:
    :return:
    """
    if not context or len(context) == 0:
        return text
    template = Template(text)
    return template.render(**context)


def trans_size_str_to_mb(size: str):
    """
    把一个字符串格式的文件尺寸单位，转换成MB单位的标准数字
    :param size:
    :return:
    """
    if not size:
        return 0.0
    s = None
    u = None
    if size.find(' ') != -1:
        arr = size.split(' ')
        s = arr[0]
        u = arr[1]
    else:
        if size.endswith('GB'):
            s = size[0:-2]
            u = 'GB'
        elif size.endswith('GiB'):
            s = size[0:-3]
            u = 'GB'
        elif size.endswith('MB'):
            s = size[0:-2]
            u = 'MB'
        elif size.endswith('MiB'):
            s = size[0:-3]
            u = 'MB'
        elif size.endswith('KB'):
            s = size[0:-2]
            u = 'KB'
        elif size.endswith('KiB'):
            s = size[0:-3]
            u = 'KB'
        elif size.endswith('TB'):
            s = size[0:-2]
            u = 'TB'
        elif size.endswith('TiB'):
            s = size[0:-3]
            u = 'TB'
        elif size.endswith('PB'):
            s = size[0:-2]
            u = 'PB'
        elif size.endswith('PiB'):
            s = size[0:-3]
            u = 'PB'
    if not s:
        return 0.0
    if s.find(',') != -1:
        s = s.replace(',', '')
    return trans_unit_to_mb(float(s), u)


def trans_unit_to_mb(size: float, unit: str) -> float:
    """
    按文件大小尺寸规格，转换成MB单位的数字
    :param size:
    :param unit:
    :return:
    """
    if unit == 'GB' or unit == 'GiB':
        return round(size * 1024, 2)
    elif unit == 'MB' or unit == 'MiB':
        return round(size, 2)
    elif unit == 'KB' or unit == 'KiB':
        return round(size / 1024, 2)
    elif unit == 'TB' or unit == 'TiB':
        return round(size * 1024 * 1024, 2)
    elif unit == 'PB' or unit == 'PiB':
        return round(size * 1024 * 1024 * 1024, 2)
    else:
        return size


class DictWrapper(dict):
    """对字典类的一个包装，提供一些固定值类型获取的方法，增强部分值获取的兼容性"""

    def get_value(self, key, default_value=None):
        if self.get(key) is None:
            return default_value
        return self.get(key)

    def get_int(self, key, default_value: int = None):
        if self.get(key) is None:
            return default_value
        try:
            ss = str(self.get(key)).replace(',', '')
            return int(ss)
        except Exception as e:
            return default_value

    def get_float(self, key, default_value: float = None):
        if self.get(key) is None:
            return default_value
        try:
            ss = str(self.get(key)).replace(',', '')
            return float(ss)
        except Exception as e:
            return default_value
