import os
import sys

import yaml
from yaml.loader import SafeLoader
from .defdict import DefDict
from typing import Self

class Config(DefDict):
    def __init__(self, path: str = None, role: str = None, parent: Self = None):

        super(Config, self).__init__()

        self.path = path
        self.role = role
        self.parent = parent

        # config_path = os.environ.get("EXACT_CONFIG", find_config())
      
        # print(f"Load config {self.path}, parent: {parent}")

        self._make_default_config()

        try:
            if self.path:
                with open(self.path) as f:
                    self._d.update(yaml.safe_load(f))
        
        except (yaml.YAMLError, TypeError) as e:
            print(f"YAML error in {self.path}: {e}")

        self.inherit()

        if role == "master":
            self.init_master_config()
        
    def _make_default_config(self):
        self._d = {
            'tokens': list(),
            'trusted_ips': list(),
            'datasets': dict(),
            'sandbox': False,
            'sandbox_expire': 3600 * 24
        }

        if self.role == "dataset":
            self._d['format'] = "json"
            self._d['search'] = dict()
            self._d['limit'] = 20


    def inherit(self):
        """ inherit settings from parent config """
        if self.parent:
            # we are project or dataset config
            if self.parent['tokens']:
                self._d['tokens'].extend(self.parent['tokens'])

    def init_master_config(self):
        # apply env variables
        if os.environ.get('SASHIMI_DATASET'):
            for dsline in os.environ.get('SASHIMI_DATASET').split(' '):
                ds_name, ds_location = dsline.split(':', maxsplit=1)
                if ds_location.startswith('http://') or ds_location.startswith('https://'):
                    self._d['datasets'][ds_name] = {
                        "url": ds_location
                    }
                else:
                    self._d['datasets'][ds_name] = {
                        "file": ds_location
                    }

        if os.environ.get('SASHIMI_TOKEN'):
            # add token
            self._d['tokens'].append(os.environ.get('SASHIMI_TOKEN'))

        if os.environ.get('SASHIMI_TRUSTED_IP'):
            # add token
            self._d['trusted_ips'].extend(os.environ.get('SASHIMI_TRUSTED_IP').split(' '))

        if os.environ.get('SASHIMI_IP_HEADER'):
            # add token
            self._d['ip_header'] = os.environ.get('SASHIMI_IP_HEADER')



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
        return f"Config: {self._d}"

    def __len__(self):
        return len(self._d)

    def __delitem__(self, key):
        del self._d[key]

    def __contains__(self, key):
        return key in self._d
    
    def __repr__(self):
        return(f"Config({self.role}) tokens: {self['tokens']}")