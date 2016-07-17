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


class DropObject(TableObject):
    mutate_attributes = {"xp": None,
                         "gp": None,
                         }


class MonsterObject(TableObject):
    mutate_attributes = {"hp": (0, 0xFFFE),
                         "strength": None,
                         "defense": None,
                         "speed": None,
                         "magic": None,
                         }
    intershuffle_attributes = [
        "resistances", "weaknesses",
        ]

    @property
    def intershuffle_valid(self):
        return False

    @property
    def is_boss(self):
        return self.index >= 57

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

    def mutate(self):
        oldstats = {}
        for key in self.mutate_attributes:
            oldstats[key] = getattr(self, key)
        super(MonsterObject, self).mutate()
        if self.is_boss:
            for (attr, oldval) in oldstats.items():
                if getattr(self, attr) < oldval:
                    setattr(self, attr, oldval)
        for attr in ["resistances", "weaknesses", "immunities"]:
            if self.is_boss and attr == "immunities":
                continue
            value = getattr(self, attr)
            numbits = bin(value).count("1")
            digits = random.sample(range(8), numbits)
            newvalue = 0
            for d in digits:
                newvalue |= (1 << d)
        while random.choice([True, False]):
            attr = random.choice(["resistances", "weaknesses", "immunities"])
            value = getattr(self, attr)
            if attr != "immunities" and bin(value).count("1") > 6:
                continue
            flag = (1 << random.randint(0, 7))
            if ((attr == "weaknesses" or not self.is_boss) and
                    random.randint(1, 10) == 10):
                value ^= flag
            else:
                if attr != "immunities" and bin(value).count("1") > 4:
                    continue
                value |= flag
        if random.randint(1, 4) == 4:
            self.counter &= 0x0F
            newcounter = random.choice([0, 0, 0x10, 0x20, 0x40, 0x80, 0x80])
            self.counter |= newcounter


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
    minmax = lambda x: (min(x), max(x))
    for m in MonsterObject.every:
        print m.index, m.name, " ".join(map(hexify, m.unknown)), m.hp
    clean_and_write(ALL_OBJECTS)
    rewrite_snes_meta("FFMQ-R", VERSION, megabits=32)
    finish_interface()
