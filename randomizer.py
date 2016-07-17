from randomtools.tablereader import TableObject
from randomtools.utils import (
    classproperty, mutate_normal,
    utilrandom as random)
from randomtools.interface import (
    get_outfile, run_interface, rewrite_snes_meta,
    clean_and_write, finish_interface)


RANDOMIZE = True
VERSION = 1
ALL_OBJECTS = None

texttable = {}
TEXTTABLEFILE = "mq.tbl"
for line in open(TEXTTABLEFILE):
    a, b = line.strip("\n").split("=")
    a = int(a, 0x10)
    texttable[a] = b


def bytes_to_text(data):
    return "".join([texttable[d] if d in texttable else "~" for d in data])


class TreasureIndexObject(TableObject): pass
class WeaponObject(TableObject): pass
class AttackObject(TableObject): pass
class ArmorObject(TableObject): pass
class DropObject(TableObject): pass


class MonsterObject(TableObject):
    @property
    def name(self):
        return MonsterNameObject.get(self.index).name

    @property
    def drop(self):
        return DropObject.get(self.index)

    @property
    def xp(self):
        return self.drop.xp * 3

    @property
    def gp(self):
        return self.drop.gp * 3


class TreasureObject(TableObject): pass
class BattleRewardObject(TableObject): pass
class MonsterNameObject(TableObject):
    @property
    def name(self):
        return bytes_to_text(self.text)


class CharacterObject(TableObject): pass


class BattleRoundsObject(TableObject):
    flag = "b"
    flag_description = "battlefields"
    mutate_attributes = {"num_rounds": (0, 0xFF)}


if __name__ == "__main__":
    print ("You are using the FF Mystic Quest randomizer "
           "version %s." % VERSION)
    ALL_OBJECTS = [g for g in globals().values()
                   if isinstance(g, type) and issubclass(g, TableObject)
                   and g not in [TableObject]]
    run_interface(ALL_OBJECTS, snes=True)
    hexify = lambda x: "{0:0>2}".format("%x" % x)
    numify = lambda x: "{0: >3}".format(x)
    for m in MonsterObject.every:
        print m.name, m.xp, m.gp
    import pdb; pdb.set_trace()
    minmax = lambda x: (min(x), max(x))
    clean_and_write(ALL_OBJECTS)
    rewrite_snes_meta("FFMQ-R", VERSION, megabits=32)
    finish_interface()
