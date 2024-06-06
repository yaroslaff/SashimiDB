import os
import time
import yaml
from yaml.loader import SafeLoader
from pathlib import Path
import string
import random

from typing import Dict


from .dataset import Dataset
from .config import Config
from .defdict import DefDict
from .exception import ProjectExistsException

from evalidate import EvalModel

class Project(DefDict):

    _d: Dict[str, Dataset]

    def __init__(self, de: os.DirEntry, model: EvalModel, app_config: Config):

        super(Project, self).__init__()

        self.de = de
        # self.datadir = os.path.join(de, 'data')
        self.name = de.name
        self.model = model
        self.datasets = dict()
        self.app_config = app_config
        self.config = None
        self.path = str(de)

        self.read_config()

        for datafile in os.scandir(de):

            if datafile.name.startswith('_'):
                continue

            if not datafile.name.endswith('.json'):
                continue


            dsname = os.path.splitext(datafile.name)[0]

            self._d[dsname] = Dataset(name = dsname, project=self, 
                                      path = datafile.path,
                                      model=self.model)

    def get_config_path(self) -> str:
        return os.path.join(self.de, '__project.yml')

    def read_config(self):
        try:
            self.config = Config(self.get_config_path(), role="project", parent = self.app_config)
        except FileNotFoundError:
            self.config = Config(role="project", parent=self.app_config)


    def __repr__(self):
        return f'Project {self.name!r} ({" ".join(self._d)})'
    
    def is_sandbox(self):
        return self.config['sandbox']
    
    def cron(self):
        if self.is_sandbox():
            now = time.time()            
            delete = list()
            for dsname, ds in self._d.items():
                if ds.is_local():
                    # local datasets never expire
                    continue
                
                if now > ds.loaded + self.config['sandbox_expire']:
                    delete.append(dsname)
            for dsname in delete:
                del self._d[dsname]
    
    @staticmethod
    def create(de: os.DirEntry):        
        config = Config(role="project", inherit=False)
        config.save(de / '__project.yml')

    def new_key(self):

        # get NOT-INHERITED config
        config = Config(self.get_config_path(), inherit=False)

        token = "".join(random.choices(string.ascii_letters + string.digits, k=50))
        if not 'tokens' in self.config:
            config['tokens'] = list()
        config['tokens'].append(token)
        config.save()

        self.read_config()

        return token

class Projects():

    projects: dict[str, Project]    

    def __init__(self):
        self.path = None
        self.projects = dict()
        self.app_config = None
        self.last_cron = time.time()
        self.cron_period = 10

    @property
    def config(self):
        return self.app_config
    
    @config.setter
    def config(self, config):
        self.app_config = config

    def create(self, name: str):
        pdir = self.path / name

        if pdir.exists():
            raise ProjectExistsException(f"project {name!r} already exists")
        
        pdir.mkdir(parents=False)
        apikey = Project.create(pdir)
        p = Project(pdir, model=self.model, app_config=self.app_config)
        self.projects[name] = p
        apikey = p.new_key()
        return apikey

    def read(self, path: str, model: EvalModel):
        self.path = Path(path)
        self.model = model

        print(f"load projects from path {path!r}")

        for tdir in os.scandir(self.path):
            if tdir.is_dir():
                self.projects[tdir.name] = Project(tdir, model=self.model, app_config=self.app_config)

    def cron(self):

        if time.time() < self.last_cron + self.cron_period:
            return

        for p in self:
            p.cron()
        self.last_cron = time.time()

    def __setitem__(self, key, item):
        self.projects[key] = item

    def __getitem__(self, key):
        return self.projects[key]

    def __repr__(self):
        return f"Projects({len(self.projects)})"

    def __len__(self):
        return len(self.projects)

    def __delitem__(self, key):
        del self.projects[key]

    def __iter__(self):
        yield from self.projects.values()
    
projects = Projects()