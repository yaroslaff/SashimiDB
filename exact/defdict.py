
class DefDict:
    def __init__(self, init=None, ):
        self._d = init or dict()
        if hasattr(self, 'set_defaults'):
            self.set_defaults()

    def __setitem__(self, key, item):
        self._d[key] = item

    def __getitem__(self, key):
        return self._d[key]

    def get(self, key, default=None):
        try:
            return self._d[key]
        except KeyError:
            return default

    def __repr__(self):
        return f"{self.__class__.__name__}: {self._d}"

    def __len__(self):
        return len(self._d)

    def __delitem__(self, key):
        del self._d[key]

    def __contains__(self, key):
        return key in self._d