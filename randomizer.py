from randomtools.tablereader import TableObject
from randomtools.utils import (
    classproperty, mutate_normal, shuffle_bits,
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


class CombatObject(object):
    mutate_attributes = {"power": None}

    def mutate(self):
        super(CombatObject, self).mutate()
        self.status = shuffle_bits(self.status)


class WeaponObject(CombatObject, TableObject):
    flag = "c"
    intershuffle_attributes = ["statboost", "status"]

    @property
    def rank(self):
        return self.power

    def mutate(self):
        super(WeaponObject, self).mutate()
        if random.randint(1, 3) == 3:
            element = (1 << random.randint(3, 7))
            self.element |= element


class AttackObject(CombatObject, TableObject):
    flag = "m"


class ArmorObject(CombatObject, TableObject):
    flag = "c"
    intershuffle_attributes = ["statboost", "element", "status"]

    @property
    def rank(self):
        return self.power

    def mutate(self):
        super(ArmorObject, self).mutate()
        if random.randint(1, 4) == 4:
            self.element = shuffle_bits(self.element)
        else:
            value = shuffle_bits(self.element >> 3, size=5)
            value = value << 3
            self.element = self.element & 0x7
            self.element |= value


class DropObject(TableObject):
    flag = "t"
    flag_description = "treasure"
    mutate_attributes = {"xp": None,
                         "gp": None,
                         }


class MonsterObject(TableObject):
    flag = "m"
    flag_description = "monster stats"
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
            value = shuffle_bits(value)
            setattr(self, attr, value)
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
            setattr(self, attr, value)
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


class CharacterObject(TableObject):
    flag = "c"
    flag_description = "characters"
    mutate_attributes = {"level": (1, 99),
                         "max_hp": (1, 32000),
                         "attack": (1, 99),
                         "defense": (1, 99),
                         "speed": (1, 99),
                         "magic": (1, 99),
                         "accuracy": (1, 99),
                         "white": (0, 99),
                         "black": (0, 99),
                         "wizard": (0, 99),
                         }
    intershuffle_attributes = [
        "max_hp", "attack", "defense", "speed", "magic", "accuracy",
        ("white", "black", "known_magic"), ("wizard", "known_wizard")]

    @property
    def rank(self):
        return self.level

    @property
    def name(self):
        return bytes_to_text(self.name_text)

    @property
    def known_black(self):
        return self.known_magic & 0xF

    @property
    def known_white(self):
        return self.known_magic >> 4

    def mutate(self):
        self.known_magic = shuffle_bits(self.known_magic)
        known_wizard = self.known_wizard >> 4
        self.known_wizard = shuffle_bits(known_wizard, size=4) << 4
        super(CharacterObject, self).mutate()

    def cleanup(self):
        self.current_hp = self.max_hp
        for attr in ["attack", "defense", "speed", "magic"]:
            setattr(self, "%s2" % attr, getattr(self, attr))
        if ((self.known_white and self.black and
                not self.white and not self.known_black) or
                (self.known_black and self.white and
                    not self.black and not self.known_white)):
            self.white, self.black = self.black, self.white
        if "DemoPlay" in self.name:
            return
        for attr in ["white", "black", "wizard"]:
            if getattr(self, "known_%s" % attr):
                avg = (self.white + self.black + self.wizard) / 3
                avg = max(avg, 1)
                setattr(self, attr, max(getattr(self, attr), avg))
            else:
                setattr(self, attr, 0)


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
    clean_and_write(ALL_OBJECTS)
    for c in CharacterObject.every:
        print c.name, "%x" % c.known_magic, c.white, c.black, "%x" % c.known_wizard, c.wizard
    rewrite_snes_meta("FFMQ-R", VERSION, megabits=32)
    finish_interface()
