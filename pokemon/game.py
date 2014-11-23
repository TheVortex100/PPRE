
import json
import os

import ndstool
from ctr.header_bin import HeaderBin as CTRHeaderBin
from ntr.header_bin import HeaderBin as NTRHeaderBin
from ntr.narc import NARC
from util import cached_property
from util import BinaryIO
from generic.editable import Editable

GAME_CODES = {
    'ADA': 'Diamond',
    'APA': 'Pearl',
    'CPU': 'Platinum',
    'IPK': 'HeartGold',
    'IPG': 'SoulSilver',
    'IRB': 'Black',
    'IRA': 'White',
    'IRE': 'Black2',
    'IRD': 'White2',
    'EKJ': 'X',
    'EK2': 'Y',
    'ECR': 'OmegaRuby',
    'ECL': 'AlphaSapphire'
}

REGION_CODES = {
    'E': 'US',
    'O': 'US',
    'J': 'JP',
    'A': 'EU',
    'P': 'EU',
    'K': 'KO'
}

GEN_IV = ('Diamond', 'Pearl', 'Platinum', 'HeartGold', 'SoulSilver')
GEN_V = ('Black', 'White', 'Black2', 'White2')
GEN_VI = ('X', 'Y', 'OmegaRuby', 'AlphaSapphire')


class Project(Editable):
    def __init__(self):
        self.name = 'Project'
        self.restrict('name')
        self.description = 'Description'
        self.restrict('description')
        self.version = 0.1
        self.restrict('version')


class Files(Editable):
    def __init__(self, directory):
        self.base = ''
        self.restrict('base')
        self.directory = directory
        self.restrict('directory')


class Game(Editable):
    """A Loaded Game Instance

    """
    def __init__(self):
        self.files = None
        self.restrict('files')
        self.project = Project()
        self.restrict('project')
        self.game_name = None
        self.game_code = None
        self.region_code = None
        self.header = None
        self.config = {}

    @staticmethod
    def from_workspace(workspace):
        files = Files(workspace)
        try:
            # NTR
            handle = open(os.path.join(files.directory, 'header.bin'))
        except:
            # CTR
            with open(os.path.join(files.directory, 'ncch_header.bin')) as handle2:
                header = CTRHeaderBin(handle2)
        else:
            header = NTRHeaderBin(handle)
            handle.close()
        game_code = header.base_code[:3]
        region_code = header.base_code[3]
        try:
            game_name = GAME_CODES[game_code]
        except:
            raise ValueError('Unknown game code: '+game_code)
        if game_name in ('Diamond', 'Pearl'):
            game = DPGame()
        elif game_name == 'Platinum':
            game = PtGame()
        elif game_name in ('HeartGold', 'SoulSilver'):
            game = HGSSGame()
        elif game_name in ('Black', 'White'):
            game = BWGame()
        elif game_name in ('Black2', 'White2'):
            game = B2W2Game()
        elif game_name in ('X', 'Y'):
            game = XYGame()
        elif game_name in ('OmegaRuby', 'AlphaSapphire'):
            game = ORASGame()
        game.files = files
        game.game_name = game_name
        game.game_code = game_code
        game.region_code = region_code
        game.header = header
        game.load_config()
        return game

    @staticmethod
    def from_file(filename, parent_directory):
        """Creates a workspace from a ROM

        Returns
        -------
        game : Game

        Raises
        ------
        IOError
            If the new workspace already exists
        """
        tail = os.path.split(filename)[1]
        name, ext = os.path.splitext(tail)
        ext = ext.lower()
        workspace = os.path.join(parent_directory, name)
        os.mkdir(workspace)  # Let raise IOError
        if ext in ('.3ds', '.3dz'):
            raise NotImplementedError('CTR dumping not implemented')
        elif ext == '.nds':
            ndstool.dump(filename, workspace)
        else:
            raise ValueError('Not able to detect file type')
        game = Game.from_workspace(workspace)
        game.write_config()
        return game

    def load_config(self):
        try:
            with open(os.path.join(self.files.directory, 'config.json'))\
                    as handle:
                self.from_dict(json.load(handle))
        except IOError as err:
            print(err)

    def write_config(self):
        with open(os.path.join(self.files.directory, 'config.json'), 'w')\
                as handle:
            json.dump(self.to_dict(), handle)

    def archive(self, filename):
        return NARC(open(os.path.join(self.files.directory, 'fs', filename)))

    def save_archive(self, archive, filename):
        with open(os.path.join(self.files.directory, 'fs', filename), 'wb')\
                as handle:
            archive.save(BinaryIO.adapter(handle))

    @cached_property
    def personal_archive(self):
        return self.archive(self.personal_archive_file)

    def get_personal(self, natid):
        return self.personal_archive.files[natid]

    def set_personal(self, natid, data):
        self.personal_archive.files[natid] = data
        self.save_archive(self.personal_archive, self.personal_archive_file)

    @cached_property
    def evo_archive(self):
        return self.archive(self.evo_archive_file)

    def get_evo(self, natid):
        return self.evo_archive.files[natid]

    def set_evo(self, natid, data):
        self.evo_archive.files[natid] = data
        self.save_archive(self.evo_archive, self.evo_archive_file)

    @cached_property
    def wotbl_archive(self):
        return self.archive(self.wotbl_archive_file)

    def get_wotbl(self, natid):
        return self.wotbl_archive.files[natid]

    def set_wotbl(self, natid, data):
        self.wotbl_archive.files[natid] = data
        self.save_archive(self.wotbl_archive, self.wotbl_archive_file)

    def save(self):
        pass


class DPGame(Game):
    evo_archive_file = 'poketool/personal/evo.narc'
    personal_archive_file = 'poketool/personal/personal.narc'
    wotbl_archive_file = 'poketool/personal/wotbl.narc'

    def __init__(self):
        super(DPGame, self).__init__()


class PtGame(DPGame):
    personal_archive_file = 'poketool/personal/pl_personal.narc'

    def __init__(self):
        super(PtGame, self).__init__()


class HGSSGame(Game):
    evo_archive_file = 'a/0/3/4'
    personal_archive_file = 'a/0/0/2'
    wotbl_archive_file = 'a/0/3/3'

    def __init__(self):
        super(HGSSGame, self).__init__()


class BWGame(Game):
    evo_archive_file = 'a/0/1/9'
    personal_archive_file = 'a/0/1/6'
    wotbl_archive_file = 'a/0/1/8'

    def __init__(self):
        super(BWGame, self).__init__()


class B2W2Game(BWGame):
    def __init__(self):
        super(B2W2Game, self).__init__()


class XYGame(Game):
    evo_archive_file = 'a/2/1/5'
    personal_archive_file = 'a/2/1/8'
    wotbl_archive_file = 'a/2/1/4'

    def __init__(self):
        super(XYGame, self).__init__()


class ORASGame(XYGame):
    def __init__(self):
        super(ORASGame, self).__init__()
