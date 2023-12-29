import os
import time
import yaml
from yaml.loader import SafeLoader

from typing import Dict

from .dataset import Dataset
from .config import Config
from .defdict import DefDict

from evalidate import EvalModel

class Project(DefDict):

    _d: Dict[str, Dataset]

    def __init__(self, de: os.DirEntry, model: EvalModel, app_config: Config):

        super(Project, self).__init__()

        self.de = de
        # self.datadir = os.path.join(de, 'data')
        self.name = de.name
        self.model = model
        self.config_path = os.path.join(de, '__project.yml')
        self.datasets = dict()
        self.app_config = app_config
        self.config = None
        self.path = de.path

        try:
            self.config = Config(self.config_path, role="project", parent = self.app_config)
        except FileNotFoundError:
            self.config = Config(role="project", parent=self.app_config)

        for datafile in os.scandir(de):

            if datafile.name.startswith('_'):
                continue

            if not datafile.name.endswith('.json'):
                continue


            dsname = os.path.splitext(datafile.name)[0]

            self._d[dsname] = Dataset(name = dsname, project=self, 
                                      path = datafile.path,
                                      model=self.model)

    def __repr__(self):
        return f'Project {self.name!r} ({" ".join(self._d)})'
    
    def is_sandbox(self):
        return self.config['sandbox']
    
    def cron(self):
        if self.is_sandbox():
            now = time.time()            
            delete = list()
            for dsname, ds in self._d.items():
                if now > ds.loaded + self.config['sandbox_expire']:
                    delete.append(dsname)
            for dsname in delete:
                del self._d[dsname]

class Projects():

    projects: dict[str, Project]    

    def __init__(self):
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

    def read(self, path: str, model: EvalModel):

        print(f"load projects from path {path!r}")

        for tdir in os.scandir(path):
            if tdir.is_dir():
                self.projects[tdir.name] = Project(tdir, model=model, app_config=self.app_config)

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