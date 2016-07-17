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
    a, b = line.split("=")
    a = int(a, 0x10)
    texttable[a] = b


def bytes_to_text(data):
    return "".join([texttable[d] if d in texttable else "~" for d in data])


class TreasureIndexObject(TableObject): pass
class WeaponObject(TableObject): pass
class AttackObject(TableObject): pass
class ArmorObject(TableObject): pass
class MonsterObject(TableObject): pass
class TreasureObject(TableObject): pass
class BattleRewardObject(TableObject): pass
class MonsterNameObject(TableObject): pass
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
    import pdb; pdb.set_trace()
    minmax = lambda x: (min(x), max(x))
    clean_and_write(ALL_OBJECTS)
    rewrite_snes_meta("FFMQ-R", VERSION, megabits=32)
    finish_interface()
